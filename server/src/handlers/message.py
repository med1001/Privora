from db import get_db
from models import Message, OfflineMessage
import json
import traceback

async def handle_incoming_message(sender_email, websocket, data):
    db = next(get_db())
    msg_type = data.get("type")

    print(f"[WS INCOMING] ({sender_email}) {msg_type} → {data}")

    if msg_type == "message":
        recipient_email = data.get("to")
        message = data.get("message")
        from_display_name = data.get("fromDisplayName", sender_email)  # ✅ Get display name from frontend, fallback to email

        if not recipient_email or not message:
            print(f"[WS ERROR] Missing 'to' or 'message' → {data}")
            return

        # ✅ Store in Message table with from_display_name
        try:
            db.add(Message(sender=sender_email, recipient=recipient_email, message=message, sender_display_name=from_display_name))
            db.commit()
            print(f"[DB] ✅ Stored → {sender_email} → {recipient_email}")
        except Exception as e:
            print(f"[DB ERROR] Failed to store → {e}")
            traceback.print_exc()

        # ✅ Deliver to online recipient if possible
        try:
            from main import active_connections
            if recipient_email in active_connections:
                await active_connections[recipient_email].send_text(json.dumps({
                    "type": "message",
                    "from": sender_email,
                    "fromDisplayName": from_display_name,
                    "to": recipient_email,
                    "message": message
                }))
                print(f"[WS DELIVERY] ✅ Sent to online user → {recipient_email}")
            else:
                db.add(OfflineMessage(sender=sender_email, recipient=recipient_email, message=message, sender_display_name=from_display_name))
                db.commit()
                print(f"[WS OFFLINE STORAGE] → {recipient_email}")
        except Exception as e:
            print(f"[WS ERROR] Delivery/store failed → {e}")
            traceback.print_exc()

    elif msg_type == "login":
        print(f"[WS LOGIN] Retrieving offline + history for {sender_email}")

        try:
            # ✅ Retrieve and send offline messages
            offline_messages = db.query(OfflineMessage).filter_by(recipient=sender_email).all()
            for msg in offline_messages:
                await websocket.send_text(json.dumps({
                    "type": "offline",
                    "from": msg.sender,
                    "to": msg.recipient,
                    "message": msg.message,
                    "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
                }))
                db.delete(msg)
            db.commit()
            print(f"[WS OFFLINE DELIVERY] ✅ Completed → {sender_email}")

            # ✅ Retrieve full history with fromDisplayName
            history = db.query(Message).filter(
                (Message.sender == sender_email) | (Message.recipient == sender_email)
            ).order_by(Message.timestamp.asc()).all()

            history_payload = [{
                "from": msg.sender,
                "fromDisplayName": msg.sender_display_name or msg.sender,  # ✅ Include display name in history
                "to": msg.recipient,
                "message": msg.message,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
            } for msg in history]

            await websocket.send_text(json.dumps({
                "type": "history",
                "messages": history_payload
            }))
            print(f"[WS HISTORY] ✅ Sent history ({len(history_payload)} messages)")

        except Exception as e:
            print(f"[WS ERROR] History retrieval → {e}")
            traceback.print_exc()

    else:
        print(f"[WS WARNING] Unknown message type '{msg_type}' → {data}")