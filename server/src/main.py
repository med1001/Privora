# Destructive: Drops all tables first (for testing/dev only!)
# Base.metadata.drop_all(bind=engine)
# Base.metadata.create_all(bind=engine)

import os
import json
import time
import uuid
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, Query, File, UploadFile
from fastapi.staticfiles import StaticFiles
import uuid, shutil, os
from fastapi.middleware.cors import CORSMiddleware
from firebase_admin import auth as firebase_auth, credentials, initialize_app
from src.db import engine
from src.models import Base
from src.handlers.message import handle_incoming_message

# ---------- Load environment ----------
load_dotenv()

# ---------- Firebase Initialization ----------
cred_path = os.getenv("FIREBASE_ADMIN_CREDENTIALS_JSON")
if not cred_path:
    raise Exception("Set FIREBASE_ADMIN_CREDENTIALS_JSON environment variable to your Firebase Admin SDK JSON file path")

cred = credentials.Certificate(cred_path)
initialize_app(cred)

# ---------- Database Initialization ----------
#Base.metadata.drop_all(bind=engine)  # Remove this in production!
Base.metadata.create_all(bind=engine)

# ---------- FastAPI App ----------
app = FastAPI()

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3001,http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = {}  # user_email -> {connection_id: websocket}
pending_calls = {}       # call_id -> {call_id, from, to, data, created_at, expires_at}
call_sessions = {}       # call_id -> {call_id, caller, callee, status, created_at, expires_at, ...}


def prune_expired_call_state():
    now = time.time()

    for call_id, offer in list(pending_calls.items()):
        if offer.get("expires_at", 0) <= now:
            pending_calls.pop(call_id, None)
            session = call_sessions.get(call_id)
            if session and session.get("status") in {"offering", "queued", "ringing"}:
                call_sessions.pop(call_id, None)

    for call_id, session in list(call_sessions.items()):
        expires_at = session.get("expires_at")
        if expires_at and expires_at <= now and session.get("status") in {"offering", "queued", "ringing"}:
            call_sessions.pop(call_id, None)
            pending_calls.pop(call_id, None)


def is_user_online(user_email: str) -> bool:
    return bool(active_connections.get(user_email))


async def send_to_user(user_email: str, payload: dict):
    user_connections = active_connections.get(user_email, {})
    stale_connection_ids = []

    for connection_id, ws in list(user_connections.items()):
        try:
            await ws.send_text(json.dumps(payload))
        except Exception as e:
            print(f"[WS SEND ERROR] Failed to send to {user_email}/{connection_id}: {e}")
            stale_connection_ids.append(connection_id)

    for connection_id in stale_connection_ids:
        user_connections.pop(connection_id, None)

    if not user_connections:
        active_connections.pop(user_email, None)


async def broadcast_presence(user_email: str, status: str):
    """Notify all connected clients that a given user went online/offline."""
    if not active_connections:
        return

    payload = json.dumps({
        "type": "presence",
        "userId": user_email,
        "status": status,
    })

    for other_user, connections in list(active_connections.items()):
        for connection_id, ws in list(connections.items()):
            try:
                await ws.send_text(payload)
            except Exception as e:
                print(f"[WS PRESENCE ERROR] Failed to send to {other_user}/{connection_id}: {e}")
                connections.pop(connection_id, None)

        if not connections:
            active_connections.pop(other_user, None)

# ---------- Token Verification ----------
def verify_token(token: str):
    try:
        decoded = firebase_auth.verify_id_token(token)
        return decoded['uid'], decoded.get('email')
    except Exception as e:
        print(f"[AUTH ERROR] {e}")
        return None, None

def get_current_user(authorization: str = Header(...)):
    token = authorization.replace("Bearer ", "")
    uid, email = verify_token(token)
    if not email:
        raise HTTPException(status_code=401, detail="Invalid token")
    return email

# ---------- Routes ----------

@app.get("/search-users")
def search_users(q: str = Query(..., min_length=1), user_email: str = Depends(get_current_user)):
    query = q.strip().lower()
    matched_users = []
    page = firebase_auth.list_users()

    while page:
        for user in page.users:
            display_name = (user.display_name or "").strip()
            email = (user.email or "").strip()
            if query in display_name.lower():
                matched_users.append({
                    "userId": email,
                    "displayName": display_name
                })
        page = page.get_next_page()

    return matched_users

@app.get("/ws_test")
def websocket_test(user_email: str = Depends(get_current_user)):
    return {
        "message": "WebSocket connection secured!",
        "email": user_email
    }

@app.websocket("/ws")
@app.websocket("/ws/")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    print("[WS] Connection opened")

    user_email = None
    connection_id = uuid.uuid4().hex

    try:
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)
            prune_expired_call_state()

            # --- Ping/Pong Keep-Alive ---
            if data_json.get("type") == "ping":
                print(f"[WS PING] Keep-alive received from {user_email or 'unauthenticated_user'}")
                await websocket.send_text(json.dumps({"type": "pong"}))
                continue

            if data_json.get("type") == "login":
                token = data_json.get("token")
                uid, email = verify_token(token)
                user_email = email or uid
                if not user_email:
                    await websocket.close(code=1008)
                    print("[WS AUTH FAIL] Invalid token")
                    return

                print(f"[WS LOGIN SUCCESS] {user_email}")
                had_existing_connections = is_user_online(user_email)
                active_connections.setdefault(user_email, {})[connection_id] = websocket

                # Notify all clients that this user is now online
                if not had_existing_connections:
                    await broadcast_presence(user_email, "online")

                # Send the new client a snapshot of who is currently online
                for other_email, other_connections in active_connections.items():
                    if other_email == user_email:
                        continue
                    if not other_connections:
                        continue
                    try:
                        await websocket.send_text(json.dumps({
                            "type": "presence",
                            "userId": other_email,
                            "status": "online",
                        }))
                    except Exception as e:
                        print(f"[WS PRESENCE SNAPSHOT ERROR] {e}")

            if user_email:
                await handle_incoming_message(user_email, websocket, data_json)

    except WebSocketDisconnect:
        print(f"[WS DISCONNECTED] {user_email if user_email else 'Unknown user'}")
        if user_email:
            user_connections = active_connections.get(user_email, {})
            user_connections.pop(connection_id, None)
            if not user_connections:
                active_connections.pop(user_email, None)

                affected_call_ids = []
                for call_id, session in list(call_sessions.items()):
                    if session.get("caller") != user_email and session.get("callee") != user_email:
                        continue

                    counterpart = session.get("callee") if session.get("caller") == user_email else session.get("caller")
                    affected_call_ids.append(call_id)
                    if counterpart and is_user_online(counterpart):
                        await send_to_user(counterpart, {
                            "type": "call_end",
                            "from": user_email,
                            "to": counterpart,
                            "callId": call_id,
                            "reason": "peer_disconnected",
                        })

                for call_id in affected_call_ids:
                    pending_calls.pop(call_id, None)
                    call_sessions.pop(call_id, None)

                await broadcast_presence(user_email, "offline")
    except Exception as e:
        print(f"[WS ERROR] {e}")
        if user_email:
            user_connections = active_connections.get(user_email, {})
            user_connections.pop(connection_id, None)
            if not user_connections:
                active_connections.pop(user_email, None)

                affected_call_ids = []
                for call_id, session in list(call_sessions.items()):
                    if session.get("caller") != user_email and session.get("callee") != user_email:
                        continue

                    counterpart = session.get("callee") if session.get("caller") == user_email else session.get("caller")
                    affected_call_ids.append(call_id)
                    if counterpart and is_user_online(counterpart):
                        await send_to_user(counterpart, {
                            "type": "call_end",
                            "from": user_email,
                            "to": counterpart,
                            "callId": call_id,
                            "reason": "peer_disconnected",
                        })

                for call_id in affected_call_ids:
                    pending_calls.pop(call_id, None)
                    call_sessions.pop(call_id, None)

                await broadcast_presence(user_email, "offline")


MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB limit
ALLOWED_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.pdf', '.doc', '.docx', '.txt', '.mp4', '.mp3', '.webm', '.csv'}

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), user_email: str = Depends(get_current_user)):
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided.")
    
    try:
        file_extension = os.path.splitext(file.filename)[1].lower()
        if file_extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=415, detail=f"Format {file_extension} not allowed.")

        unique_filename = f"{uuid.uuid4().hex}{file_extension}"
        file_path = os.path.join("uploads", unique_filename)

        file_size = 0
        with open(file_path, "wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024) # 1MB memory chunks
                if not chunk:
                    break
                file_size += len(chunk)
                if file_size > MAX_FILE_SIZE:
                    buffer.close()
                    os.remove(file_path) # Clean up partial file immediately
                    raise HTTPException(status_code=413, detail="File too large. Maximum is 10MB.")
                buffer.write(chunk)

        return {"url": f"/uploads/{unique_filename}", "filename": file.filename, "type": file.content_type}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
