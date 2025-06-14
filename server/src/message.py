# handlers/message.py
from db import get_db
from models import Message, OfflineMessage
import json
import traceback

async def handle_incoming_message(sender_email, websocket, data):
    db = next(get_db())
    msg_type = data.get("type")

    print(f"\n[INCOMING] ({sender_email}) Received '{msg_type}' → {data}")

    if msg_type == "message":
        recipient_email = data.get("to")
        message = data.get("message")

        if not recipient_email or not message:
            print(f"[ERROR] ({sender_email}) Missing 'to' or 'message' → {data}")
            return

        print(f"[MESSAGE] {sender_email} → {recipient_email}: {message}")

        # Store message in history
        try:
            db.add(Message(sender=sender_email, recipient=recipient_email, message=message))
            db.commit()
            print(f"[DB] ✅ Message stored → {sender_email} → {recipient_email}")
        except Exception as e:
            print(f"[ERROR] ({sender_email}) ❌ Failed to store message → {e}")
            traceback.print_exc()

        # Deliver to online recipient or store offline
        try:
            from main import active_connections  # Avoid circular imports
            if recipient_email in active_connections:
                payload = {
                    "type": "message",
                    "from": sender_email,
                    "to": recipient_email,
                    "message": message
                }
                await active_connections[recipient_email].send_text(json.dumps(payload))
                print(f"[DELIVERY] ✅ Sent to online user → '{recipient_email}'")
            else:
                db.add(OfflineMessage(sender=sender_email, recipient=recipient_email, message=message))
                db.commit()
                print(f"[OFFLINE STORAGE] 💾 Stored offline → '{recipient_email}'")
        except Exception as e:
            print(f"[ERROR] ({sender_email}) ❌ Delivery/store failed for '{recipient_email}' → {e}")
            traceback.print_exc()

    elif msg_type == "login":
        print(f"[LOGIN] ({sender_email}) User logged in → Retrieving offline messages")
        try:
            offline_messages = db.query(OfflineMessage).filter_by(recipient=sender_email).all()
            print(f"[LOGIN] ({sender_email}) Found {len(offline_messages)} offline message(s)")

            for msg in offline_messages:
                print(f"[OFFLINE DELIVERY] ({sender_email}) Sending from '{msg.sender}' → '{msg.recipient}': {msg.message}")
                await websocket.send_text(json.dumps({
                    "type": "offline",
                    "from": msg.sender,
                    "to": msg.recipient,
                    "message": msg.message
                }))
                db.delete(msg)

            db.commit()
            print(f"[LOGIN] ✅ Finished delivering offline messages → ({sender_email})")

        except Exception as e:
            print(f"[ERROR] ({sender_email}) ❌ Retrieving/sending offline failed → {e}")
            traceback.print_exc()

    else:
        print(f"[WARNING] ({sender_email}) ⚠️ Unknown message type: '{msg_type}' → {data}")
