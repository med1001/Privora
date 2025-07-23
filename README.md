![Logo](assets/logo.png)

#  Privora

**Privora** is a real-time chat backend powered by FastAPI, Firebase Authentication, and WebSockets. It includes secure token-based login, message persistence (with offline delivery), and a Dockerized setup for easy development and deployment.

![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![Firebase](https://img.shields.io/badge/Firebase-ffca28?style=for-the-badge&logo=firebase)
![WebSockets](https://img.shields.io/badge/WebSockets-333333?style=for-the-badge&logo=websockets&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-2496ED?style=for-the-badge&logo=docker&logoColor=white)

![Lines of Code](https://img.shields.io/badge/lines_of_code-543-brightgreen)
![GitHub issues](https://img.shields.io/github/issues/med1001/Privora)
![GitHub stars](https://img.shields.io/github/stars/med1001/Privora)
![GitHub pull requests](https://img.shields.io/github/issues-pr/med1001/Privora)
![GitHub license](https://img.shields.io/github/license/med1001/Privora)

---

##  Features

-  Firebase Authentication
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

You can use the firebase_credentials.example.json file in src/ as a template for creating your own firebase_credentials.json.
Make sure to set the correct ALLOWED_ORIGIN in your backend to avoid CORS errors during development and production. This should match the origin of your frontend app (e.g., http://localhost:3000 or your deployed frontend URL).

---

##  Docker Usage

###  Build the Docker Image

From the project root:

```bash
docker build -t privora-backend .
```

###  Run the Container

####  Running the Backend with Docker

If you're using a **reverse proxy** (like Nginx or Traefik), you **do not need to expose a port** with `-p` — the reverse proxy will handle traffic forwarding through the internal Docker network.

However, if you're **running locally without a reverse proxy**, you **must expose the port** to access the backend directly via the browser (e.g., at `http://localhost:8000`). In that case, use the following command:

```bash
docker run --env-file ./server/.env -v "${PWD}/server:/app" -p 8000:8000 privora-backend
```

####  Flag Breakdown:

```
--env-file ./server/.env # Loads environment variables into the container.
-v $(pwd)/server:/app    # For development: mount local code into the container
-p 8000:8000             # Exposes container port 8000 to your host machine. Only needed when not using a reverse proxy.
--network privora-net    # (optional) Connects the container to a specific Docker network. Use this if you're working with other containers (e.g., database, reverse proxy).
```

> 🛠️ If using `--network privora-net`, you **must create the network first** (only once):

```bash
docker network create privora-net
```

> 📌 On **Windows**:
> - In **CMD**, replace `$(pwd)` with `%cd%`
> - In **PowerShell**, use `"${PWD}/server:/app"`

---


##  Deployment Architecture (Multi-Container with Reverse Proxy)

This project is designed to run as **three coordinated Docker containers** on a shared network:

| Container        | Role                     | Exposed Port  | Internal Hostname  |
|------------------|--------------------------|---------------|--------------------|
| `frontend`       | React app                |               |  `frontend`        |
| `backend`        | FastAPI                  |               |   `backend`        |
| `reverse-proxy`  | NGINX Reverse Proxy      |**80**(for now)| n/a                |

---

###   NGINX Routing Overview

The reverse proxy (`reverse-proxy` container using NGINX) handles all external traffic and routes requests as follows:

| Request Path    | Routed To      | Description                |
|-----------------|----------------|----------------------------|
| `/`             | `frontend:80`  | Static frontend app        |
| `/api/`         | `backend:8000` | FastAPI REST API endpoints |
| `/ws`           | `backend:8000/ws` | WebSocket connection   |

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

For simpler orchestration, we will consider using `docker-compose.yml`later.

---

##  Development Notes

- SQLite used by default
- Can switch `DATABASE_URL` in `db.py`
- You may optionally drop and recreate tables:
  ```python
  # Base.metadata.drop_all(bind=engine)
  ```

---

## Contributing
Feel free to contribute! Fork the repo, make your changes, and submit a pull request.

---

##  License

This project is open-source and available under the GNU General Public License v3.0.

---

