FROM python:3.12-slim

# System dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr \
    tesseract-ocr-eng \
    libmagic1 \
    libpq-dev \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (layer cache)
COPY pyproject.toml ./
RUN pip install --no-cache-dir hatchling && \
    pip install --no-cache-dir -e .

# Copy application code
COPY . .

# Create vault mount point
RUN mkdir -p /vault

# Create LightRAG working directory
RUN mkdir -p /app/lightrag-data

EXPOSE 8010 8011

CMD ["uvicorn", "gnosis.main:app", "--host", "0.0.0.0", "--port", "8010"]
