FROM python:3.11-slim

# Install system dependencies (adjust as needed, kept sqlite3 for SQLAlchemy)
RUN apt-get update && apt-get install -y \
    libsqlite3-dev sqlite3 \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the FastAPI application code
COPY src/ ./src/

# Expose FastAPI port
EXPOSE 8080

# Run FastAPI with uvicorn
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8080"]
