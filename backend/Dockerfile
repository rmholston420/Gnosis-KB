FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    tesseract-ocr \
    libmagic1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy ALL source first so editable install can find the package
COPY . .

# Upgrade pip, install deps from pyproject.toml, then gunicorn/uvicorn
RUN pip install --no-cache-dir --upgrade pip setuptools wheel \
 && pip install --no-cache-dir -e . \
 && pip install --no-cache-dir gunicorn "uvicorn[standard]"

EXPOSE 8010

CMD ["sh", "-c", "alembic upgrade head && uvicorn gnosis.main:app --host 0.0.0.0 --port 8010 --workers 2"]
