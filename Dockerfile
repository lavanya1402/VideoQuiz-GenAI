# Use the same Python as your venv
FROM python:3.11-slim

# Keep images small & predictable
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# ffmpeg for audio extraction (and tini for clean shutdowns)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg tini curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first for better layer caching
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy app
COPY . .

# Streamlit settings
EXPOSE 8501
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_SERVER_ADDRESS=0.0.0.0 \
    STREAMLIT_SERVER_PORT=8501

ENTRYPOINT ["tini", "--"]
CMD ["streamlit", "run", "streamlit_app.py", "--server.enableCORS=false", "--server.enableXsrfProtection=false"]
