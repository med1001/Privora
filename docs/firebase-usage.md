# Firebase Usage (Current + Required Additions)

This document maps how Firebase is currently used in Privora and what should be added in Firebase Console for mobile push notifications.

## Important

This repo audit shows code-level usage. It does **not** read your private Firebase Console state.

## Current Firebase Usage

### 1) Backend (`Privora/server`)

- Uses **Firebase Admin SDK** for server-side auth verification and user directory queries.
- Uses **Firebase Cloud Messaging (FCM)** for incoming-call push notifications.

Where this is implemented:

- `server/src/main.py`
  - Initializes Admin SDK with `FIREBASE_ADMIN_CREDENTIALS_JSON`.
  - Verifies bearer tokens using `firebase_auth.verify_id_token`.
  - Searches users via `firebase_auth.list_users`.
  - Exposes push token APIs:
    - `POST /api/push/register`
    - `POST /api/push/unregister`
- `server/src/handlers/message.py`
  - Triggers push delivery on `call_offer` via `push_service.notify_incoming_call(...)`.
- `server/src/push.py`
  - Sends FCM messages with Android/APNS config.
  - Stores device tokens in in-memory registry (non-durable; single-instance scope).
- `server/.env.example`
  - Defines `FIREBASE_ADMIN_CREDENTIALS_JSON=./src/firebase_credentials.json`.
- `server/src/firebase_credentials.example.json`
  - Template for Admin service account JSON.

### 2) Web client (`Privora-GUI`)

- Uses **Firebase Web SDK** for client authentication.
- Config is expected in `src/firebase-config.ts` (generated from example).

Where this is implemented:

- `Privora-GUI/src/firebase-config.example.ts`
  - Initializes Firebase App + Auth using web config (`apiKey`, `projectId`, etc).

## What To Add In Firebase Console Now

If you currently only configured a **Web app** for auth, add platform app registrations in the **same Firebase project**:

1. **Android app registrations**
   - Production package: `com.privora.mobile`.
   - Development package: `com.privora.mobile.debug`.
   - Register both apps in the same Firebase project so development and production can use the same Authentication and backend data while remaining distinct Android applications.
   - Download the refreshed multi-client `google-services.json` and place it at `Privora-Mobile/google-services.json`. Expo/EAS copies the matching client into the generated Android project.
   - The legacy `com.anonymous.PrivoraMobile` client may remain in Firebase temporarily, but new builds no longer use it.

2. **(Optional but recommended) iOS app registration**
   - Bundle ID must match iOS app.
   - Download `GoogleService-Info.plist`.
   - Add it to iOS project.

3. **Cloud Messaging readiness**
   - Ensure Cloud Messaging is enabled for the same project.
   - Keep using Admin SDK service account on backend for sending FCM.

## Existing vs Target (Push Token Storage)

### Existing

- Push tokens are stored in process memory in `server/src/push.py`.
- Works for one backend process.
- Tokens are lost on restart and not shared across replicas.

### Target

- Replace in-memory token registry with durable shared storage (Firestore suggested).
- Keep current small token interface (`register`, `unregister`, `tokens_for`, `discard`) for low-impact migration.

## Console Verification Checklist

Use this quick check in Firebase Console:

- Project has:
  - Web app (already used for auth in GUI)
  - Production Android app: `com.privora.mobile`
  - Development Android app: `com.privora.mobile.debug`
  - (Optional) iOS app
- Authentication:
  - Required sign-in provider(s) enabled
- Cloud Messaging:
  - Enabled for the project
- Service account:
  - Backend JSON key exists and matches current project
- Security:
  - Service account JSON is not committed to git

## Files Referenced

- `server/src/main.py`
- `server/src/handlers/message.py`
- `server/src/push.py`
- `server/.env.example`
- `server/src/firebase_credentials.example.json`
- `Privora-GUI/src/firebase-config.example.ts`
