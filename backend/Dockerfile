FROM python:3.11-slim

# Install curl for healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Upgrade pip and install numpy first (pandas needs it for metadata generation)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir numpy==1.26.4 && \
    pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create data directory for dataset storage
RUN mkdir -p /data/datasets

EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}
