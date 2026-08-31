FROM python:3.12-slim

WORKDIR /app

# Install runtime system dependencies:
# - curl: for container health checks
# - tesseract-ocr & tesseract-ocr-eng: system OCR engine
# - libglib2.0-0: for OpenCV headless image processing
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    tesseract-ocr \
    tesseract-ocr-eng \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user and setup directories
RUN useradd -m -u 1000 appuser && \
    mkdir -p /app/temp && \
    chown -R appuser:appuser /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .
RUN chown -R appuser:appuser /app

USER appuser

# Configurable service port
ENV PORT=8001 \
    APP_ENV=production \
    LOG_LEVEL=INFO \
    TEMP_DIR=/app/temp \
    MAX_UPLOAD_SIZE_MB=25

EXPOSE 8001

# Healthcheck checking /health endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:${PORT}/health || exit 1

# Start FastAPI application with Uvicorn
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
