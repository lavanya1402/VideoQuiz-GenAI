# ===== Base image =====
FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg ca-certificates curl build-essential tini \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install deps first (layer cache)
COPY requirements.txt .
RUN pip install --upgrade pip && pip install --no-cache-dir -r requirements.txt

# Copy app
COPY streamlit_app.py ./streamlit_app.py
# COPY assets ./assets  # (agar assets folder ho to uncomment)

# Streamlit defaults (headless + bind to 0.0.0.0)
ENV STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHERUSAGESTATS=false \
    STREAMLIT_SERVER_PORT=8501

# Some platforms read PORT env; keep it explicit
ENV PORT=8501

EXPOSE 8501

ENTRYPOINT ["tini", "--"]
CMD ["streamlit", "run", "streamlit_app.py", "--server.address=0.0.0.0", "--server.port=8501"]
