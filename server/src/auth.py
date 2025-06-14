# auth.py
import firebase_admin
from firebase_admin import credentials, auth

cred = credentials.Certificate("firebase_credentials.json")
firebase_admin.initialize_app(cred)

def verify_token(token: str):
    try:
        decoded = auth.verify_id_token(token)
        return decoded['uid'], decoded.get('email')
    except Exception as e:
        print(f"[AUTH ERROR] {e}")
        return None, None
