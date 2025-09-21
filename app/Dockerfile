FROM python:3.12-slim

WORKDIR /app

# Copy requirements first for better Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy application code
COPY s3wrap.py main.py ./

# Default command to run uvicorn server
CMD uvicorn main:app --host 0.0.0.0 --port ${APP_PORT:-8080}