FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for Chromium + Xvfb
RUN apt-get update && apt-get install -y \
    wget curl gnupg xvfb \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 \
    libgbm1 libasound2 libpangocairo-1.0-0 libpango-1.0-0 libcairo2 \
    fonts-liberation libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Upgrade pip and install Python deps
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install --upgrade playwright

# Install Playwright browsers (Chromium, Firefox, WebKit)
RUN playwright install --with-deps

COPY . .

# Expose Render’s dynamic port
ENV PORT=8000
EXPOSE $PORT

# Run FastAPI with uvicorn
CMD ["xvfb-run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
