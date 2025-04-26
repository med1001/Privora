from flask import Flask, request, jsonify
import sqlite3
import jwt
import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
from datetime import datetime, timedelta, timezone
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os
from dotenv import load_dotenv
from functools import wraps
from flask_cors import CORS

app = Flask(__name__)

# Load environment variables
load_dotenv()

# CORS Configuration
ALLOWED_ORIGIN = os.getenv("ALLOWED_ORIGIN", "http://localhost:3000")
CORS(app, resources={r"/*": {"origins": [ALLOWED_ORIGIN], "supports_credentials": True}})

app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "your_default_secret")

# Database setup
DB_FILE = "users.db"

def init_db():
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE,
                email TEXT UNIQUE,
                password TEXT,
                verified INTEGER DEFAULT 0,
                verification_token TEXT,
                expiration_time TEXT
            )
        ''')
        conn.commit()

init_db()

# Email Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = os.getenv("SMTP_PORT")
SMTP_USERNAME = os.getenv("SMTP_USERNAME")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
FROM_EMAIL = os.getenv("FROM_EMAIL")

def send_verification_email(email, token):
    try:
        # Create email content
        subject = "Verify Your Email"
        body = f"Click the link to verify your email: http://127.0.0.1:5000/verify/{token}"

        # Create the email message
        msg = MIMEMultipart()
        msg['From'] = FROM_EMAIL
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Send the email via SMTP
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(FROM_EMAIL, email, msg.as_string())

        print(f"Email sent to {email}")
    except Exception as e:
        print(f"Error sending email: {str(e)}")

# Registration Route
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username, email, password = data['username'], data['email'], data['password']

    hashed_password = generate_password_hash(password)
    verification_token = str(uuid.uuid4())
    expiration_time = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO users (username, email, password, verification_token, expiration_time) VALUES (?, ?, ?, ?, ?)",
                           (username, email, hashed_password, verification_token, expiration_time))
            conn.commit()
            send_verification_email(email, verification_token)
            return jsonify({"message": "User registered! Check email for verification link."}), 201
        except sqlite3.IntegrityError:
            return jsonify({"error": "Username or email already exists"}), 400

# Email Verification Route
@app.route('/verify/<token>', methods=['GET'])
def verify_email(token):
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE verification_token = ?", (token,))
        user = cursor.fetchone()

        if not user:
            return jsonify({"error": "Invalid token"}), 400

        expiration_time = datetime.fromisoformat(user[6])
        if datetime.now(timezone.utc) > expiration_time:
            return jsonify({"error": "Token expired, please request a new one."}), 400

        cursor.execute("UPDATE users SET verified = 1 WHERE verification_token = ?", (token,))
        conn.commit()
        return jsonify({"message": "Email verified! You can now log in."}), 200

# Login Route
@app.route('/login', methods=['POST'])
def login():
    data = request.json
    username, password = data['username'], data['password']

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT password, verified FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()

        if user and check_password_hash(user[0], password):
            if user[1] == 1:
                token = jwt.encode({'username': username, 'exp': datetime.utcnow() + timedelta(hours=2)},
                                   app.config['SECRET_KEY'], algorithm="HS256")
                return jsonify({"message": "Login successful", "token": token}), 200
            else:
                return jsonify({"error": "Email not verified"}), 403
        return jsonify({"error": "Invalid credentials"}), 401

# ✅ New: Search Users Route
@app.route("/search-users", methods=["GET"])
@token_required
def search_users():
    query = request.args.get("q", "").strip().lower()
    if not query:
        return jsonify([])  # Return empty list if no query

    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT username FROM users WHERE LOWER(username) LIKE ? AND verified = 1", (f"%{query}%",))
        users = [row[0] for row in cursor.fetchall()]
    
    return jsonify(users)

# Secure WebSocket Test Route
@app.route('/ws_test', methods=['GET'])
@token_required
def websocket_test():
    return jsonify({"message": "WebSocket connection secured!", "user": request.user}), 200

if __name__ == "__main__":
    app.run(debug=True)
