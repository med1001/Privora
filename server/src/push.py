"""FCM push-notification helpers.

We rely on `firebase-admin` (already initialised in `main.py`) to deliver
high-priority "incoming call" notifications to the recipient's device, so the
phone rings even when the app is closed.

For development we store registered device tokens in memory. Production
deployments should replace `_TokenRegistry` with a Firestore (or other
durable) backend and persist `(user_email, token, platform)` tuples. The
public surface is intentionally tiny so swapping the backend is easy.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from typing import Iterable, Optional

try:
    from firebase_admin import messaging
    from firebase_admin.exceptions import FirebaseError
except Exception:  # pragma: no cover - firebase-admin is a hard dependency in main
    messaging = None  # type: ignore[assignment]
    FirebaseError = Exception  # type: ignore[assignment]

logger = logging.getLogger("privora.push")


@dataclass(frozen=True)
class DeviceToken:
    user_email: str
    token: str
    platform: str  # "android" | "ios" | "web"


class _TokenRegistry:
    """Thread-safe in-memory store for FCM device tokens.

    Maps `user_email -> { token: platform }`. Idempotent; a token is owned by
    exactly one user (the latest registration wins, mimicking what FCM itself
    enforces server-side).
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._by_user: dict[str, dict[str, str]] = {}
        self._owner_of_token: dict[str, str] = {}

    def register(self, user_email: str, token: str, platform: str) -> None:
        if not user_email or not token:
            return
        with self._lock:
            previous_owner = self._owner_of_token.get(token)
            if previous_owner and previous_owner != user_email:
                self._by_user.get(previous_owner, {}).pop(token, None)
                if not self._by_user.get(previous_owner):
                    self._by_user.pop(previous_owner, None)
            self._by_user.setdefault(user_email, {})[token] = platform
            self._owner_of_token[token] = user_email

    def unregister(self, token: str) -> None:
        if not token:
            return
        with self._lock:
            owner = self._owner_of_token.pop(token, None)
            if owner:
                tokens = self._by_user.get(owner)
                if tokens:
                    tokens.pop(token, None)
                    if not tokens:
                        self._by_user.pop(owner, None)

    def tokens_for(self, user_email: str) -> list[DeviceToken]:
        with self._lock:
            tokens = self._by_user.get(user_email, {})
            return [DeviceToken(user_email, token, platform) for token, platform in tokens.items()]

    def discard(self, tokens: Iterable[str]) -> None:
        for token in tokens:
            self.unregister(token)


_registry = _TokenRegistry()


def register_token(user_email: str, token: str, platform: str) -> None:
    """Public registration entry point used by the HTTP API."""
    _registry.register(user_email, token, (platform or "android").lower())


def unregister_token(token: str) -> None:
    """Public removal entry point used by the HTTP API."""
    _registry.unregister(token)


def has_tokens(user_email: str) -> bool:
    return bool(_registry.tokens_for(user_email))


def _build_call_message(token: str, *, call_id: str, from_email: str, from_display_name: str) -> "messaging.Message":
    """Build a high-priority *data-only* FCM message for an incoming call.

    The mobile client renders a rich Notifee notification with Answer /
    Decline action buttons (and a full-screen intent on Android) when the
    background data handler runs. We deliberately do NOT include a
    `notification` block, otherwise Android would auto-display a plain alert
    with no action buttons before our handler has a chance to take over.

    Reserved data keys (`from`, `notification`, `message_type`, anything
    starting with `google` / `gcm`) must NOT be used here - FCM rejects them
    with INVALID_ARGUMENT.
    """
    # `direct_boot_ok=True` allows the message to be delivered while the
    # device is still in direct-boot mode (locked after reboot, before
    # the user enters credentials), which trims a few seconds off the
    # ring time on devices that just woke up.
    android_kwargs: dict = {
        "priority": "high",
        "ttl": 45,  # ringing timeout - irrelevant after that.
    }
    try:
        android_config = messaging.AndroidConfig(
            **android_kwargs,
            direct_boot_ok=True,
        )
    except TypeError:
        # firebase-admin < 6.4 does not support direct_boot_ok; fall
        # back to the older signature.
        android_config = messaging.AndroidConfig(**android_kwargs)

    apns_config = messaging.APNSConfig(
        headers={
            "apns-priority": "10",
            "apns-push-type": "background",
        },
        payload=messaging.APNSPayload(
            aps=messaging.Aps(content_available=True),
        ),
    )

    return messaging.Message(
        token=token,
        data={
            "type": "incoming_call",
            "callId": call_id,
            "fromUserId": from_email,
            "fromDisplayName": from_display_name or from_email,
        },
        android=android_config,
        apns=apns_config,
    )


def notify_incoming_call(
    *,
    to_user_email: str,
    from_email: str,
    from_display_name: str,
    call_id: str,
) -> int:
    """Send an incoming-call notification to every registered device.

    Returns the number of successful deliveries. Tokens that FCM rejects as
    invalid are removed from the registry.
    """
    if messaging is None:
        logger.warning("firebase-admin messaging is unavailable; push not sent")
        return 0

    targets = _registry.tokens_for(to_user_email)
    if not targets:
        return 0

    successes = 0
    invalid_tokens: list[str] = []

    for target in targets:
        try:
            message = _build_call_message(
                target.token,
                call_id=call_id,
                from_email=from_email,
                from_display_name=from_display_name,
            )
            messaging.send(message)
            successes += 1
        except FirebaseError as exc:
            code = getattr(exc, "code", None) or getattr(getattr(exc, "cause", None), "code", None)
            text_code = str(code or "")
            if text_code in {"registration-token-not-registered", "invalid-argument"} or "Requested entity was not found" in str(exc):
                invalid_tokens.append(target.token)
            logger.warning("[PUSH] FCM send failed for %s (%s): %s", to_user_email, text_code or "unknown", exc)
        except Exception as exc:  # pragma: no cover - defensive; never break call flow
            logger.warning("[PUSH] Unexpected FCM error for %s: %s", to_user_email, exc)

    if invalid_tokens:
        _registry.discard(invalid_tokens)

    return successes


def _build_cancel_message(token: str, *, call_id: str) -> "messaging.Message":
    """Build a high-priority data-only FCM message that asks the device to
    dismiss any in-flight incoming-call notification for `call_id`.

    Sent when the caller hangs up, the call is rejected by another device,
    or the server-side ringing TTL elapses, so the callee's phone stops
    ringing immediately rather than waiting for the local 45 s timeout.
    """
    android_kwargs: dict = {
        "priority": "high",
        "ttl": 30,
    }
    try:
        android_config = messaging.AndroidConfig(
            **android_kwargs,
            direct_boot_ok=True,
        )
    except TypeError:
        android_config = messaging.AndroidConfig(**android_kwargs)

    apns_config = messaging.APNSConfig(
        headers={
            "apns-priority": "10",
            "apns-push-type": "background",
        },
        payload=messaging.APNSPayload(
            aps=messaging.Aps(content_available=True),
        ),
    )

    return messaging.Message(
        token=token,
        data={
            "type": "cancel_call",
            "callId": call_id,
        },
        android=android_config,
        apns=apns_config,
    )


def notify_cancel_call(*, to_user_email: str, call_id: str) -> int:
    """Tell the recipient's devices to dismiss the incoming-call heads-up.

    Returns the number of successful deliveries. Best-effort - failures
    are logged but do not raise.
    """
    if messaging is None:
        return 0

    targets = _registry.tokens_for(to_user_email)
    if not targets:
        return 0

    successes = 0
    invalid_tokens: list[str] = []
    for target in targets:
        try:
            messaging.send(_build_cancel_message(target.token, call_id=call_id))
            successes += 1
        except FirebaseError as exc:
            code = getattr(exc, "code", None) or getattr(getattr(exc, "cause", None), "code", None)
            text_code = str(code or "")
            if text_code in {"registration-token-not-registered", "invalid-argument"} or "Requested entity was not found" in str(exc):
                invalid_tokens.append(target.token)
            logger.warning("[PUSH] cancel_call send failed for %s (%s): %s", to_user_email, text_code or "unknown", exc)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("[PUSH] Unexpected cancel_call error for %s: %s", to_user_email, exc)

    if invalid_tokens:
        _registry.discard(invalid_tokens)

    return successes


def registry_snapshot() -> dict[str, list[str]]:
    """Diagnostic helper: returns `{user_email: [token, ...]}`."""
    with _registry._lock:  # noqa: SLF001 - debug helper
        return {user: list(tokens.keys()) for user, tokens in _registry._by_user.items()}


def reset_registry() -> None:  # pragma: no cover - test helper
    """Clear all registered tokens. Intended for tests only."""
    global _registry
    _registry = _TokenRegistry()


__all__ = [
    "DeviceToken",
    "has_tokens",
    "notify_cancel_call",
    "notify_incoming_call",
    "register_token",
    "registry_snapshot",
    "reset_registry",
    "unregister_token",
]
