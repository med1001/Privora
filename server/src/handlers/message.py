from src.db import get_db
from src.models import Message, OfflineMessage
from firebase_admin import auth as firebase_auth
import json
import traceback

async def handle_incoming_message(sender_email, websocket, data):
    db = next(get_db())
    msg_type = data.get("type")

    print(f"[WS INCOMING] ({sender_email}) {msg_type} → {data}")

    if msg_type == "message":
        recipient_email = data.get("to")
        message = data.get("message")
        msg_id = data.get("msg_id", "")  # Get front-end generated ID
        from_display_name = data.get("fromDisplayName", sender_email)  # ✅ Get display name from frontend, fallback to email

        if not recipient_email or not message:
            print(f"[WS ERROR] Missing 'to' or 'message' → {data}")
            return

        # ✅ Store in Message table with from_display_name
        msg_timestamp_iso = None
        try:
            new_msg = Message(sender=sender_email, recipient=recipient_email, message=message, sender_display_name=from_display_name, msg_id=msg_id)
            db.add(new_msg)
            db.commit()
            db.refresh(new_msg)
            if new_msg.timestamp:
                msg_timestamp_iso = new_msg.timestamp.isoformat()
            print(f"[DB] ✅ Stored → {sender_email} → {recipient_email}")
        except Exception as e:
            print(f"[DB ERROR] Failed to store → {e}")
            traceback.print_exc()

        # ✅ Deliver to online recipient if possible
        try:
            from src.main import active_connections
            if recipient_email in active_connections:
                await active_connections[recipient_email].send_text(json.dumps({
                    "type": "message",
                    "msg_id": msg_id,
                    "from": sender_email,
                    "fromDisplayName": from_display_name,
                    "to": recipient_email,
                    "message": message,
                    "timestamp": msg_timestamp_iso
                }))
                print(f"[WS DELIVERY] ✅ Sent to online user → {recipient_email}")
            else:
                db.add(OfflineMessage(sender=sender_email, recipient=recipient_email, message=message, sender_display_name=from_display_name, msg_id=msg_id))
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
                    "msg_id": msg.msg_id,
                    "from": msg.sender,
                    "to": msg.recipient,
                    "message": msg.message,
                    "reactions": json.loads(msg.reactions) if msg.reactions else {},
                      "timestamp": msg.timestamp.isoformat() if hasattr(msg, "timestamp") and msg.timestamp else None
                }))
                db.delete(msg)
            db.commit()
            print(f"[WS OFFLINE DELIVERY] ✅ Completed → {sender_email}")

            # ✅ Retrieve history with fromDisplayName, limiting to last 25.
            # We want the newest 25, so we order descending, limit, then reverse back to chronological.
            history_query = db.query(Message).filter(
                (Message.sender == sender_email) | (Message.recipient == sender_email)
            ).order_by(Message.timestamp.desc()).limit(25).all()
            
            # Reverse to make it ascending (oldest to newest) for the frontend
            history = list(reversed(history_query))

            history_payload = [{
                "msg_id": msg.msg_id,
                "from": msg.sender,
                "fromDisplayName": msg.sender_display_name or msg.sender,  # ✅ Include display name in history
                "to": msg.recipient,
                "message": msg.message,
                "reactions": json.loads(msg.reactions) if msg.reactions else {},
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
            } for msg in history]

            await websocket.send_text(json.dumps({
                "type": "history",
                "messages": history_payload
            }))
            print(f"[WS HISTORY] ✅ Sent history ({len(history_payload)} messages)")

            # ✅ Build and send a contacts list with proper display names
            other_participants = set()
            for msg in history:
                if msg.sender != sender_email:
                    other_participants.add(msg.sender)
                if msg.recipient != sender_email:
                    other_participants.add(msg.recipient)

            contacts_payload = []
            for email in other_participants:
                display_name = ""
                try:
                    user_record = firebase_auth.get_user_by_email(email)
                    display_name = (user_record.display_name or "").strip()
                except Exception as e:
                    # If lookup fails, fall back to empty and let frontend handle
                    print(f"[WS CONTACTS] Firebase lookup failed for {email}: {e}")

                contacts_payload.append({
                    "userId": email,
                    "displayName": display_name or email,
                })

            if contacts_payload:
                await websocket.send_text(json.dumps({
                    "type": "contacts",
                    "contacts": contacts_payload,
                }))
                print(f"[WS CONTACTS] ✅ Sent contacts ({len(contacts_payload)} users)")

            # ✅ Check for any pending calls 
            from src.main import pending_calls, active_connections
            if sender_email in pending_calls:
                offer_info = pending_calls.pop(sender_email)
                  import time
                  if time.time() - offer_info.get("timestamp", 0) > 45:
                      print(f"[WS SIGNALING] 🛑 Discarded expired call offer to {sender_email}")
                      pass
                  else:
                      await websocket.send_text(json.dumps(offer_info["data"]))
                      print(f"[WS SIGNALING] 🎉 Delivered queued call offer to {sender_email}")

                      # Notify the caller that they are now online and it's ringing
                      caller = offer_info["from"]
                      if caller in active_connections:
                          await active_connections[caller].send_text(json.dumps({
                              "type": "call_ring",
                              "from": sender_email,
                              "to": caller
                          }))

    elif msg_type == "reaction":
        msg_id = data.get("msg_id")
        emoji = data.get("reaction")
        recipient_email = data.get("to")

        if not msg_id or not emoji or not recipient_email:
            print(f"[WS ERROR] Missing 'msg_id', 'reaction' or 'to' for reaction → {data}")
            return

        try:
            # Update history message
            original_msg = db.query(Message).filter_by(msg_id=msg_id).first()
            if original_msg:
                reactions = json.loads(original_msg.reactions) if original_msg.reactions else {}
                reactions[sender_email] = emoji
                original_msg.reactions = json.dumps(reactions)
                db.commit()

            # Update offline message if it exists there
            offline_msg = db.query(OfflineMessage).filter_by(msg_id=msg_id).first()
            if offline_msg:
                reactions = json.loads(offline_msg.reactions) if offline_msg.reactions else {}
                reactions[sender_email] = emoji
                offline_msg.reactions = json.dumps(reactions)
                db.commit()

            print(f"[DB] ✅ Reaction updated on {msg_id}")

            # Send to recipient if online
            from src.main import active_connections
            if recipient_email in active_connections:
                await active_connections[recipient_email].send_text(json.dumps({
                    "type": "reaction",
                    "msg_id": msg_id,
                    "from": sender_email,
                    "to": recipient_email,
                    "reaction": emoji
                }))

        except Exception as e:
            print(f"[DB ERROR] Failed to store reaction → {e}")
            traceback.print_exc()

    elif msg_type in ["call_offer", "call_answer", "ice_candidate", "call_reject", "call_end", "call_ring"]:
        recipient_email = data.get("to")
        if not recipient_email:
            print(f"[WS ERROR] Missing 'to' for type {msg_type}")
            return
            
        from src.main import active_connections, pending_calls
        if recipient_email in active_connections:
            # Forward the signaling event exactly as received but with "from" added
            forward_data = data.copy()
            forward_data["from"] = sender_email
            await active_connections[recipient_email].send_text(json.dumps(forward_data))
            
            # Clean up pending calls if they end/reject/answer
            if msg_type in ["call_answer", "call_reject", "call_end"]:
                if recipient_email in pending_calls:
                    del pending_calls[recipient_email]
                if sender_email in pending_calls:
                    del pending_calls[sender_email]
                    
            print(f"[WS SIGNALING] ✅ Forwarded {msg_type} from {sender_email} to {recipient_email}")
        else:
            if msg_type == "call_offer":
                # Queue the call offer for when they log in 
                forward_data = data.copy()
                forward_data["from"] = sender_email
                import time
                  pending_calls[recipient_email] = {"from": sender_email, "data": forward_data, "timestamp": time.time()}
                
                # Tell the caller they are offline but keep ringing
                await websocket.send_text(json.dumps({
                    "type": "call_ring_offline",
                    "from": recipient_email,
                    "to": sender_email
                }))
                print(f"[WS SIGNALING] Target {recipient_email} offline. Queued call for {sender_email}")
            elif msg_type == "call_end":
                if recipient_email in pending_calls and pending_calls[recipient_email]["from"] == sender_email:
                    del pending_calls[recipient_email]
                    print(f"[WS SIGNALING] Cancelled pending call to {recipient_email}")
    else:
        print(f"[WS WARNING] Unknown message type '{msg_type}' → {data}")

