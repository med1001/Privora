FROM python:3.11-slim

# Install build tools temporarily
RUN apt-get update && apt-get install -y \
    gcc make libsqlite3-dev libwebsockets-dev libssl-dev libcjson-dev sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working dir
WORKDIR /app

# Copy & build message_core (C server)
COPY server/ ./server/
WORKDIR /app/server
RUN make

# Install Python deps for Flask
WORKDIR /app
COPY flask_auth/ ./flask_auth/
WORKDIR /app/flask_auth
RUN pip install --no-cache-dir -r requirements.txt

# Expose ports
EXPOSE 5000
EXPOSE 8080

# Launch both processes with a small supervisor
CMD ["bash", "-c", "/app/server/build/server & cd /app/flask_auth && gunicorn -w 2 -b 0.0.0.0:5000 auth_server:app > /app/gunicorn.log 2>&1"]
