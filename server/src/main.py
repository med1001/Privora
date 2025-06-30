# Destructive: Drops all tables first (for testing/dev only!)
# Base.metadata.drop_all(bind=engine)
# Base.metadata.create_all(bind=engine)

import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, Header, HTTPException, Query
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

ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[ALLOWED_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

active_connections = {}  # user_email → websocket

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

            if user_email:
                await handle_incoming_message(user_email, websocket, data_json)

    except WebSocketDisconnect:
        print(f"[WS DISCONNECTED] {user_email if user_email else 'Unknown user'}")
        active_connections.pop(user_email, None)
    except Exception as e:
        print(f"[WS ERROR] {e}")
        active_connections.pop(user_email, None)
