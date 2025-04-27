# Start from lightweight Python image
FROM python:3.11-slim

# Install necessary system packages
RUN apt-get update && apt-get install -y \
    gcc \
    make \
    libsqlite3-dev \
    libwebsockets-dev \
    libssl-dev \
    libcjson-dev \
    sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy only server and flask_auth folders
COPY server/ ./server/
COPY flask_auth/ ./flask_auth/

# Build the C server
WORKDIR /app/server
RUN make

# Install Python dependencies from requirements.txt
WORKDIR /app/flask_auth
RUN pip install --no-cache-dir -r requirements.txt

# Expose Flask API port
EXPOSE 5000    
# Expose WebSocket server port
EXPOSE 8080   

# Command to run both servers
CMD ["bash", "-c", "/app/server/build/server & python /app/flask_auth/auth_server.py"]
