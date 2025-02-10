from flask import Flask, request, jsonify
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
import uuid
import smtplib
from email.message import EmailMessage
from datetime import datetime, timedelta

app = Flask(__name__)

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
EMAIL_ADDRESS = "your-email@gmail.com"
EMAIL_PASSWORD = "your-email-password"

def send_verification_email(email, token):
    msg = EmailMessage()
    msg['Subject'] = "Verify Your Email"
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = email
    msg.set_content(f"Click the link to verify: http://127.0.0.1:5000/verify/{token}")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)

# Registration Route
@app.route('/register', methods=['POST'])
def register():
    data = request.json
    username, email, password = data['username'], data['email'], data['password']
    
    hashed_password = generate_password_hash(password)
    verification_token = str(uuid.uuid4())
    expiration_time = (datetime.utcnow() + timedelta(hours=1)).isoformat()

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
        
        expiration_time = datetime.fromisoformat(user[5])
        if datetime.utcnow() > expiration_time:
            return jsonify({"error": "Token expired"}), 400
        
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

        if user:
            if check_password_hash(user[0], password):
                if user[1] == 1:
                    return jsonify({"message": "Login successful", "user": {"username": username}}), 200
                else:
                    return jsonify({"error": "Email not verified"}), 403
            else:
                return jsonify({"error": "Invalid credentials"}), 401
        else:
            return jsonify({"error": "User not found"}), 404

if __name__ == "__main__":
    app.run(debug=True)
