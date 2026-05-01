import time
from src.db import SessionLocal
from src.models import Message, OfflineMessage
from firebase_admin import auth as firebase_auth
import json
import traceback


CALL_SIGNAL_TYPES = ["call_offer", "call_answer", "ice_candidate", "call_reject", "call_end", "call_ring", "call_accepting", "call_connected"]
CALL_SETUP_TTL_SECONDS = 45


def _cleanup_expired_calls():
    from src.main import prune_expired_call_state
    prune_expired_call_state()


def _remove_pending_call(call_id: str):
    from src.main import pending_calls
    pending_calls.pop(call_id, None)


def _close_call_session(call_id: str, final_status: str):
    from src.main import call_sessions, clear_active_call

    session = call_sessions.get(call_id)
    if session:
        session["status"] = final_status
        session["ended_at"] = time.time()

    clear_active_call(call_id)
    _remove_pending_call(call_id)
    call_sessions.pop(call_id, None)


def _is_valid_participant(session: dict, sender_email: str, recipient_email: str) -> bool:
    participants = {session.get("caller"), session.get("callee")}
    return {sender_email, recipient_email} == participants


def _get_other_party(session: dict, sender_email: str):
    if session.get("caller") == sender_email:
        return session.get("callee")
    if session.get("callee") == sender_email:
        return session.get("caller")
    return None

async def handle_incoming_message(sender_email, websocket, data):
    db = SessionLocal()
    msg_type = data.get("type")

    try:
        print(f"[WS INCOMING] ({sender_email}) {msg_type} → {data}")
        _cleanup_expired_calls()

        if msg_type == "message":
            recipient_email = data.get("to")
            message = data.get("message")
            msg_id = data.get("msg_id", "")
            from_display_name = data.get("fromDisplayName", sender_email)

            if not recipient_email or not message:
                print(f"[WS ERROR] Missing 'to' or 'message' → {data}")
                return

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

            try:
                from src.main import is_user_online, send_to_user
                if is_user_online(recipient_email):
                    await send_to_user(recipient_email, {
                        "type": "message",
                        "msg_id": msg_id,
                        "from": sender_email,
                        "fromDisplayName": from_display_name,
                        "to": recipient_email,
                        "message": message,
                        "timestamp": msg_timestamp_iso
                    })
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

                history_query = db.query(Message).filter(
                    (Message.sender == sender_email) | (Message.recipient == sender_email)
                ).order_by(Message.timestamp.desc()).limit(25).all()

                history = list(reversed(history_query))

                history_payload = [{
                    "msg_id": msg.msg_id,
                    "from": msg.sender,
                    "fromDisplayName": msg.sender_display_name or msg.sender,
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

                from src.main import pending_calls, call_sessions, is_user_online, is_user_busy, send_signaling_to_user
                pending_for_user = []
                for call_id, offer_info in list(pending_calls.items()):
                    if offer_info.get("to") != sender_email:
                        continue
                    pending_for_user.append(offer_info)
                    pending_calls.pop(call_id, None)

                for offer_info in pending_for_user:
                    call_id = offer_info["call_id"]
                    session = call_sessions.get(call_id)
                    if not session:
                        continue

                    caller = offer_info["from"]
                    if is_user_busy(sender_email, excluding_call_id=call_id):
                        if is_user_online(caller):
                            await send_signaling_to_user(caller, {
                                "type": "call_reject",
                                "from": sender_email,
                                "to": caller,
                                "callId": call_id,
                                "reason": "busy",
                            })
                        _close_call_session(call_id, "rejected")
                        continue

                    if is_user_busy(caller, excluding_call_id=call_id):
                        _close_call_session(call_id, "cancelled")
                        continue

                    await websocket.send_text(json.dumps(offer_info["data"]))
                    session["status"] = "ringing"
                    session["ringing_at"] = time.time()
                    print(f"[WS SIGNALING] 🎉 Delivered queued call offer to {sender_email} (callId={call_id})")
                    queued_signals = offer_info.get("queued_signals", [])
                    if queued_signals:
                        for queued_signal in queued_signals:
                            await websocket.send_text(json.dumps(queued_signal))
                        print(f"[WS SIGNALING] ↪ Replayed {len(queued_signals)} queued signaling message(s) to {sender_email} (callId={call_id})")

                    if is_user_online(caller):
                        await send_signaling_to_user(caller, {
                            "type": "call_ring",
                            "from": sender_email,
                            "to": caller,
                            "callId": call_id,
                        })

            except Exception as e:
                print(f"[WS ERROR] History retrieval → {e}")
                traceback.print_exc()

        elif msg_type == "reaction":
            msg_id = data.get("msg_id")
            emoji = data.get("reaction")
            recipient_email = data.get("to")

            if not msg_id or not emoji or not recipient_email:
                print(f"[WS ERROR] Missing 'msg_id', 'reaction' or 'to' for reaction → {data}")
                return

            try:
                original_msg = db.query(Message).filter_by(msg_id=msg_id).first()
                if original_msg:
                    reactions = json.loads(original_msg.reactions) if original_msg.reactions else {}
                    reactions[sender_email] = emoji
                    original_msg.reactions = json.dumps(reactions)
                    db.commit()

                offline_msg = db.query(OfflineMessage).filter_by(msg_id=msg_id).first()
                if offline_msg:
                    reactions = json.loads(offline_msg.reactions) if offline_msg.reactions else {}
                    reactions[sender_email] = emoji
                    offline_msg.reactions = json.dumps(reactions)
                    db.commit()

                print(f"[DB] ✅ Reaction updated on {msg_id}")

                from src.main import is_user_online, send_to_user
                if is_user_online(recipient_email):
                    await send_to_user(recipient_email, {
                        "type": "reaction",
                        "msg_id": msg_id,
                        "from": sender_email,
                        "to": recipient_email,
                        "reaction": emoji
                    })

            except Exception as e:
                print(f"[DB ERROR] Failed to store reaction → {e}")
                traceback.print_exc()

        elif msg_type in CALL_SIGNAL_TYPES:
            recipient_email = data.get("to")
            call_id = data.get("callId")
            if not recipient_email:
                print(f"[WS ERROR] Missing 'to' for type {msg_type}")
                return
            if not call_id:
                print(f"[WS ERROR] Missing 'callId' for type {msg_type}")
                return

            from src.main import call_sessions, pending_calls, is_user_online, is_user_busy, mark_call_active, send_signaling_to_user

            if msg_type == "call_offer":
                if call_id in call_sessions:
                    print(f"[WS SIGNALING] Duplicate call_offer ignored for callId={call_id}")
                    return

                if is_user_busy(sender_email):
                    await websocket.send_text(json.dumps({
                        "type": "call_reject",
                        "from": recipient_email,
                        "to": sender_email,
                        "callId": call_id,
                        "reason": "busy",
                    }))
                    print(f"[WS SIGNALING] Caller {sender_email} already in active call. Rejected callId={call_id}")
                    return

                if is_user_busy(recipient_email):
                    await websocket.send_text(json.dumps({
                        "type": "call_reject",
                        "from": recipient_email,
                        "to": sender_email,
                        "callId": call_id,
                        "reason": "busy",
                    }))
                    print(f"[WS SIGNALING] Callee {recipient_email} busy. Rejected callId={call_id}")
                    return

                forward_data = data.copy()
                forward_data["from"] = sender_email
                forward_data["callId"] = call_id
                now = time.time()
                expires_at = now + CALL_SETUP_TTL_SECONDS

                call_sessions[call_id] = {
                    "call_id": call_id,
                    "caller": sender_email,
                    "callee": recipient_email,
                    "status": "offering",
                    "created_at": now,
                    "expires_at": expires_at,
                }

                if is_user_online(recipient_email):
                    await send_signaling_to_user(recipient_email, forward_data)
                else:
                    call_sessions[call_id]["status"] = "queued"
                    pending_calls[call_id] = {
                        "call_id": call_id,
                        "from": sender_email,
                        "to": recipient_email,
                        "data": forward_data,
                        "queued_signals": [],
                        "created_at": now,
                        "expires_at": expires_at,
                    }
                    await websocket.send_text(json.dumps({
                        "type": "call_ring_offline",
                        "from": recipient_email,
                        "to": sender_email,
                        "callId": call_id,
                    }))
                    print(f"[WS SIGNALING] Target {recipient_email} offline. Queued call for {sender_email} (callId={call_id})")

                # Always try to wake the device via FCM. We do it for online
                # users too because the WebSocket only reaches the foreground
                # process; a high-priority push is what makes the phone ring
                # when the app is backgrounded or killed.
                try:
                    from src import push as push_service

                    display_name = (
                        data.get("fromDisplayName")
                        or sender_email
                        or "Unknown caller"
                    )
                    delivered = push_service.notify_incoming_call(
                        to_user_email=recipient_email,
                        from_email=sender_email,
                        from_display_name=str(display_name),
                        call_id=call_id,
                    )
                    if delivered:
                        print(
                            f"[PUSH] Sent incoming-call notification to {recipient_email} "
                            f"(callId={call_id}, devices={delivered})",
                            flush=True,
                        )
                except Exception as exc:  # never let push errors break call flow
                    print(f"[PUSH ERROR] {exc}", flush=True)

                if not is_user_online(recipient_email):
                    return

                print(f"[WS SIGNALING] ✅ Forwarded call_offer from {sender_email} to {recipient_email} (callId={call_id})")
                return

            session = call_sessions.get(call_id)
            if not session:
                print(f"[WS SIGNALING] Ignoring stale {msg_type}; unknown callId={call_id}")
                return

            if not _is_valid_participant(session, sender_email, recipient_email):
                print(f"[WS SIGNALING] Ignoring {msg_type}; invalid participants for callId={call_id}")
                return

            if msg_type == "call_ring":
                if session.get("callee") != sender_email or session.get("caller") != recipient_email:
                    print(f"[WS SIGNALING] Ignoring invalid call_ring direction for callId={call_id}")
                    return
                session["status"] = "ringing"
                session["ringing_at"] = time.time()
            elif msg_type == "call_accepting":
                if session.get("callee") != sender_email or session.get("caller") != recipient_email:
                    print(f"[WS SIGNALING] Ignoring invalid call_accepting direction for callId={call_id}")
                    return
                session["status"] = "accepting"
                session["accepting_at"] = time.time()
            elif msg_type == "call_answer":
                if session.get("callee") != sender_email or session.get("caller") != recipient_email:
                    print(f"[WS SIGNALING] Ignoring invalid call_answer direction for callId={call_id}")
                    return

                if is_user_busy(sender_email, excluding_call_id=call_id) or is_user_busy(recipient_email, excluding_call_id=call_id):
                    await send_signaling_to_user(sender_email, {
                        "type": "call_end",
                        "from": recipient_email,
                        "to": sender_email,
                        "callId": call_id,
                        "reason": "busy_conflict",
                    })
                    _close_call_session(call_id, "cancelled")
                    return

                session["status"] = "connected"
                session["answered_at"] = time.time()
                session["expires_at"] = None
                mark_call_active(call_id, sender_email, recipient_email)
                _remove_pending_call(call_id)
            elif msg_type == "call_connected":
                if not _is_valid_participant(session, sender_email, recipient_email):
                    print(f"[WS SIGNALING] Ignoring invalid call_connected direction for callId={call_id}")
                    return
                session["status"] = "connected"
                session["connected_at"] = time.time()
                session["expires_at"] = None
                mark_call_active(call_id, sender_email, recipient_email)
                _remove_pending_call(call_id)
            elif msg_type == "call_reject":
                _close_call_session(call_id, "rejected")
            elif msg_type == "call_end":
                _close_call_session(call_id, "ended")
            elif msg_type == "ice_candidate":
                if session.get("status") in {"ended", "rejected"}:
                    print(f"[WS SIGNALING] Ignoring ICE for closed callId={call_id}")
                    return

            if is_user_online(recipient_email):
                forward_data = data.copy()
                forward_data["from"] = sender_email
                forward_data["callId"] = call_id
                await send_signaling_to_user(recipient_email, forward_data)
                print(f"[WS SIGNALING] ✅ Forwarded {msg_type} from {sender_email} to {recipient_email} (callId={call_id})")
            else:
                if msg_type in ["call_reject", "call_end"]:
                    print(f"[WS SIGNALING] Remote user offline while closing callId={call_id}")
                    return
                if msg_type == "ice_candidate":
                    pending_offer = pending_calls.get(call_id)
                    if pending_offer and pending_offer.get("to") == recipient_email:
                        queued_signals = pending_offer.setdefault("queued_signals", [])
                        queued_signal_payload = data.copy()
                        queued_signal_payload["from"] = sender_email
                        queued_signal_payload["callId"] = call_id
                        queued_signals.append(queued_signal_payload)
                        # Avoid unbounded growth if peers keep gathering while callee is offline.
                        if len(queued_signals) > 128:
                            del queued_signals[:len(queued_signals) - 128]
                        print(f"[WS SIGNALING] Recipient offline; queued ICE candidate for callId={call_id}")
                        return
                print(f"[WS SIGNALING] Recipient offline; dropped {msg_type} for callId={call_id}")
        else:
            print(f"[WS WARNING] Unknown message type '{msg_type}' → {data}")
    finally:
        db.close()

