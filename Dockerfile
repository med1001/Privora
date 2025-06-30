FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    libsqlite3-dev sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY server/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY server/src/ ./src/
COPY server/secrets/ ./secrets/

# Expose FastAPI port
EXPOSE 8000

# ✅ Run as a Python package using `-m`, **calling python explicitly**
CMD ["python", "-m", "uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
