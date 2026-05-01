# Contributing to Privora (backend)

**Issues and pull requests for the API, WebSocket server, and database belong here.**

## Quick local setup

1. `cd server` — copy `.env.example` to `.env`.
2. Add Firebase **Admin** SDK JSON and set `FIREBASE_ADMIN_CREDENTIALS_JSON` in `.env`.
3. `pip install -r requirements.txt` then `uvicorn src.main:app --reload --host 0.0.0.0 --port 8000` (from `server/`).

## Full stack in one clone

Use [**Privora-Workspace**](https://github.com/med1001/Privora-Workspace) for submodules + Docker. See `docs/LOCAL_FULL_STACK.md` inside that repo.

## Pull requests

- Note any `.env` or schema changes.
- Describe how to verify (e.g. `/docs`, WebSocket login flow).
