![Logo](assets/logo.png)

#  Privora

**Privora** is a real-time chat backend powered by FastAPI, Firebase Authentication, and WebSockets. It includes secure token-based login, message persistence (with offline delivery), and a Dockerized setup for easy development and deployment.

![Lines of Code](https://img.shields.io/badge/lines_of_code-589-brightgreen)
![GitHub issues](https://img.shields.io/github/issues/med1001/Privora)
![GitHub stars](https://img.shields.io/github/stars/med1001/Privora)
![GitHub pull requests](https://img.shields.io/github/issues-pr/med1001/Privora)
![GitHub license](https://img.shields.io/github/license/med1001/Privora)

---

##  Features

-  Firebase Authentication (JWT)
-  WebSocket-based real-time chat
-  Offline message queuing & delivery
-  User directory search via Firebase
-  SQLite (default) or PostgreSQL via SQLAlchemy
-  Docker-based deployment

---

##  Project Structure

```
Privora/
├── assets/                        # (Optional/static frontend assets)
├── server/
│   ├── .env                       # Environment variables
│   ├── Dockerfile                 # Docker build config
│   ├── requirements.txt           # Python dependencies
│   ├── roadmap.md                 # Planning notes
│   ├── src/
│   │   ├── __init__.py
│   │   ├── auth.py                # Firebase token verification
│   │   ├── db.py                  # SQLAlchemy session config
│   │   ├── main.py                # FastAPI app & WebSocket logic
│   │   ├── models.py              # ORM Models: Message, OfflineMessage
│   │   ├── firebase_credentials.json          # Firebase Admin credentials
│   │   ├── firebase_credentials.example.json  # Sample credentials file
│   │   └── handlers/
│   │       ├── __init__.py
│   │       └── message.py         # WebSocket message handling logic
│   └── secrets/                   # (Reserved for future secrets/keys)
├── .dockerignore
├── .gitignore
└── README.md                      # You are here
```

---

##  Environment Setup

Create a `.env` file in `server/`:

```env
FIREBASE_ADMIN_CREDENTIALS_JSON=./src/firebase_credentials.json
ALLOWED_ORIGIN=http://localhost:3000
```

---

##  Docker Usage

###  Dockerfile Overview

The `Dockerfile` does the following:

- Uses `python:3.11-slim`
- Installs SQLite tools and headers
- Copies app source to `/app/src`
- Runs FastAPI app with Uvicorn

###  Build the Docker Image

From the project root:

```bash
docker build -t privora-backend .
```

###  Run the Container

```bash
docker run --env-file ./server/.env privora-backend
```

This command runs the backend container using environment variables defined in `./server/.env`.

#### ⚙️ Optional Flags

```
-v $(pwd)/server:/app    # For development: mount local code into the container
-p 8000:8000             # For local access without reverse proxy
--network privora-net    # For multi-container setup (backend, frontend, reverse proxy)
```

- Use `-v` during **development** to mount your local code. This enables hot-reloading or quick changes without rebuilding.
- Use `-p` if you're **not using a reverse proxy** and want to access the backend directly at `http://localhost:8000`.
- Use `--network privora-net` when running the backend alongside **frontend** and **reverse proxy** containers to enable internal communication by container name (e.g., `backend`, `frontend`).

> 🛠️ If using `--network privora-net`, you **must create the network first** (only once):

```bash
docker network create privora-net
```

> 📌 On **Windows**, replace `$(pwd)` with `%cd%`.

---


##  Deployment Architecture (Multi-Container with Reverse Proxy)

This project is designed to run as **three coordinated Docker containers** on a shared network:

| Container        | Role                     | Exposed Port  | Internal Hostname  |
|------------------|--------------------------|-------------- |--------------------|
| `frontend`       | React/Vite/Static HTML   | -             | `frontend`         |
| `backend`        | FastAPI WebSocket API    | 8000          | `backend`          |
| `reverse-proxy`  | NGINX Reverse Proxy      |**80**(for now)| n/a                |

---

###   NGINX Routing Overview

The reverse proxy (`reverse-proxy` container using NGINX) handles all external traffic and routes requests as follows:

| Request Path    | Routed To      | Description                |
|-----------------|----------------|----------------------------|
| `/`             | `frontend:80`  | Static frontend app        |
| `/api/`         | `backend:8000` | FastAPI REST API endpoints |
| `/ws`           | `backend:8000/ws` | WebSocket connection   |

The NGINX config also includes **WebSocket support**:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection $connection_upgrade;
```
This ensures real-time communication via WebSocket works correctly.

---

##  Docker Networking

To allow the containers to communicate by name (e.g., `frontend`, `backend`), they must all be connected to the same custom **Docker bridge network**.

You can create and run them like this:

```bash
# Create a shared Docker network (once)
docker network create privora-net

# Start each container with --network
docker run --network privora-net --name frontend ...
docker run --network privora-net --name backend ...
docker run --network privora-net --name reverse-proxy -p 80:80 ...
```

> This setup allows NGINX to forward requests to `backend:8000` and `frontend:80` without exposing those ports to the host.

For simpler orchestration, consider using `docker-compose.yml`.

---

##  WebSocket API

**Endpoint:** `/ws`

### 1️⃣ Login

```json
{
  "type": "login",
  "token": "<firebase_id_token>"
}
```

- Required as the first message
- Verifies token and registers connection
- Delivers offline messages if any

### 2️⃣ Send Message

```json
{
  "type": "message",
  "to": "receiver@example.com",
  "message": "Hi there!"
}
```

### 3️⃣ Receive Message (Live)

```json
{
  "type": "message",
  "from": "sender@example.com",
  "to": "you@example.com",
  "message": "Hi!"
}
```

### 4️⃣ Receive Offline Message

```json
{
  "type": "offline",
  "from": "sender@example.com",
  "to": "you@example.com",
  "message": "Missed this!"
}
```

---

##  REST API

### `GET /search-users?q=alice`

- Searches Firebase users by `displayName`
- Requires Authorization header

---

##  Database Models

### `Message`

| Field                | Type     |
|---------------------|----------|
| `id`                | Integer  |
| `sender`            | String   |
| `sender_display_name` | String |
| `recipient`         | String   |
| `message`           | String   |
| `timestamp`         | DateTime |

### `OfflineMessage`

Same schema as `Message`, used for undelivered messages.

---

##  Development Notes

- SQLite used by default
- Can switch `DATABASE_URL` in `db.py`
- You may optionally drop and recreate tables:
  ```python
  # Base.metadata.drop_all(bind=engine)
  ```

---

### **Contributing**
Feel free to contribute! Fork the repo, make your changes, and submit a pull request.

---

##  License

This project is open-source and available under the GNU General Public License v3.0.

---

