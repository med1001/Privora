# Destructive: Drops all tables first (for testing/dev only!)
# Base.metadata.drop_all(bind=engine)
# Base.metadata.create_all(bind=engine)

import os
import json
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

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = {}  # user_email -> websocket
pending_calls = {}       # recipient_email -> {"from": caller_email, "data": offer_data}
async def broadcast_presence(user_email: str, status: str):
    """Notify all connected clients that a given user went online/offline."""
    if not active_connections:
        return

    payload = json.dumps({
        "type": "presence",
        "userId": user_email,
        "status": status,
    })

    for ws in list(active_connections.values()):
        try:
            await ws.send_text(payload)
        except Exception as e:
            print(f"[WS PRESENCE ERROR] Failed to send to a client: {e}")

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

    try:
        while True:
            data = await websocket.receive_text()
            data_json = json.loads(data)

            if data_json.get("type") == "login":
                token = data_json.get("token")
                uid, email = verify_token(token)
                user_email = email or uid
                if not user_email:
                    await websocket.close(code=1008)
                    print("[WS AUTH FAIL] Invalid token")
                    return

                print(f"[WS LOGIN SUCCESS] {user_email}")
                active_connections[user_email] = websocket

                # Notify all clients that this user is now online
                await broadcast_presence(user_email, "online")

                # Send the new client a snapshot of who is currently online
                for other_email, other_ws in active_connections.items():
                    if other_email == user_email:
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
            active_connections.pop(user_email, None)
            
            # Clean up pending calls if caller abruptly disconnects
            for to_user, offer in list(pending_calls.items()):
                if offer["from"] == user_email:
                    del pending_calls[to_user]
                    # Also notify the callee that the call dropped so their screen stops ringing
                    if to_user in active_connections:
                        try:
                            import asyncio, json
                            asyncio.create_task(active_connections[to_user].send_text(json.dumps({
                                "type": "call_end",
                                "from": user_email,
                                "to": to_user
                            })))
                        except:
                            pass
                    # Also notify the callee that the call dropped so their screen stops ringing
                    if to_user in active_connections:
                        try:
                            import asyncio, json
                            asyncio.create_task(active_connections[to_user].send_text(json.dumps({
                                "type": "call_end",
                                "from": user_email,
                                "to": to_user
                            })))
                        except:
                            pass
                    
            await broadcast_presence(user_email, "offline")
    except Exception as e:
        print(f"[WS ERROR] {e}")
        if user_email:
            active_connections.pop(user_email, None)
            
            for to_user, offer in list(pending_calls.items()):
                if offer["from"] == user_email:
                    del pending_calls[to_user]

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
