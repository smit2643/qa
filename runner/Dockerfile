FROM python:3.11-slim

# Install Playwright system dependencies
RUN apt-get update && apt-get install -y \
    wget curl gnupg \
    libglib2.0-0 libnss3 libnspr4 libdbus-1-3 \
    libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 \
    libxfixes3 libxrandr2 libgbm1 libasound2 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright browsers
RUN playwright install chromium firefox webkit

# Copy runner + backend (shared models)
COPY . /app/runner
COPY ../backend /app/backend

ENV PYTHONPATH=/app/backend:/app

CMD ["celery", "-A", "runner.celery_app", "worker", "--loglevel=info", "--concurrency=4"]
