FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Chromium + Xvfb
RUN apt-get update && apt-get install -y \
    wget curl gnupg xvfb \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 libcairo2 \
    fonts-liberation \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install playwright
RUN playwright install --with-deps chromium
RUN pip install playwright-stealth

COPY . .

EXPOSE $PORT

# ✅ Shell form CMD so $PORT expands
CMD xvfb-run -a uvicorn main:app --host 0.0.0.0 --port $PORT
