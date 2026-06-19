# Development Guide

## Prerequisites

- Docker 24+ and Docker Compose v2
- Python 3.12+ (for local backend dev without Docker)
- Node.js 20+ (for local frontend dev without Docker)
- (Optional) Ollama installed locally or via Docker profile

## Setup

### 1. Clone and configure

```bash
git clone https://github.com/rmholston420/Gnosis-KB.git
cd Gnosis-KB
cp .env.example .env
```

Edit `.env` and set at minimum:
- `SECRET_KEY` — run `openssl rand -hex 32` to generate
- `VAULT_PATH` — absolute path to your Markdown vault directory

### 2. Start with Docker Compose

```bash
# Start all services (DB, Qdrant, API, UI)
docker compose up -d

# With local Ollama (GPU-optional)
docker compose --profile local-ai up -d
```

### 3. Run database migrations

```bash
docker exec gnosis-api alembic upgrade head
```

### 4. Access the services

| Service | URL |
|---|---|
| Web UI | http://localhost:5173 |
| API Docs (Swagger) | http://localhost:8010/docs |
| API Docs (ReDoc) | http://localhost:8010/redoc |
| Qdrant Dashboard | http://localhost:6333/dashboard |
| MCP Server | http://localhost:8011/mcp |

## Local Backend Development (without Docker)

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Set env vars
export DATABASE_URL=postgresql+asyncpg://gnosis:gnosis_dev@localhost:5432/gnosis
export QDRANT_URL=http://localhost:6333
export VAULT_PATH=/path/to/your/vault
export SECRET_KEY=your-secret-key

# Run migrations
alembic upgrade head

# Start API with hot reload
uvicorn gnosis.main:app --reload --port 8010
```

## Local Frontend Development (without Docker)

```bash
cd frontend
npm install

# Start dev server
VITE_API_BASE_URL=http://localhost:8010 npm run dev
```

## Running Tests

```bash
cd backend
pytest --cov=gnosis --cov-report=term-missing -v
```

## Ollama Models

```bash
# Pull recommended models
ollama pull qwen2.5:14b        # Primary LLM
ollama pull nomic-embed-text   # Embeddings
ollama pull llava:13b          # Optional: vision/OCR

# Minimum RAM: 16 GB for qwen2.5:14b
# Alternative (lower RAM): qwen2.5:7b
```

## Linting and Type Checking

```bash
cd backend
ruff check gnosis/
mypy gnosis/
```

```bash
cd frontend
npm run type-check
npm run lint
```

## MCP Integration (Claude Code)

```bash
claude mcp add gnosis http://localhost:8011/mcp
```

All Gnosis API endpoints are then available as MCP tools in Claude Code.
