# Gnosis Knowledge Base

> Sovereign, Linux-native, AI-augmented personal knowledge management.

[![CI](https://github.com/rmholston420/Gnosis-KB/actions/workflows/ci.yml/badge.svg)](https://github.com/rmholston420/Gnosis-KB/actions/workflows/ci.yml)

## Overview

Gnosis is a fully self-hosted personal knowledge base built on the Zettelkasten methodology with AI-powered features:

- **Plain Markdown vault** — notes live as `.md` files in `~/gnosis-vault/`
- **PARA organization** — Inbox, Zettelkasten, Projects, Areas, Resources, Archive, Journals, Sources, Meta
- **Hybrid search** — BM25 + dense vector (fastembed) → RRF fusion (Qdrant)
- **Knowledge graph** — NetworkX-powered with Cytoscape.js visualization
- **LightRAG** — graph-aware dual-level retrieval for chat
- **MCP server** — AI agents (Claude, Cursor) connect via `http://localhost:8010/mcp`
- **Multi-provider LLM** — Ollama (local) → Groq → OpenAI → OpenRouter fallback chain

## Quick Start

### 1. Clone and configure

```bash
git clone https://github.com/rmholston420/Gnosis-KB.git
cd Gnosis-KB
cp .env.example .env
# Edit .env: set VAULT_PATH, SECRET_KEY, and any API keys
```

### 2. Start with Docker Compose

```bash
docker compose up -d
```

Services:
| Service | URL |
|---------|-----|
| React UI | http://localhost:3010 |
| FastAPI (docs) | http://localhost:8010/docs |
| MCP server | http://localhost:8010/mcp |
| Qdrant UI | http://localhost:6333/dashboard |

### 3. Install Ollama models (optional but recommended)

```bash
ollama pull mistral
ollama pull nomic-embed-text
```

### 4. Connect an AI agent via MCP

In Claude Desktop `config.json`:
```json
{
  "mcpServers": {
    "gnosis-kb": {
      "url": "http://localhost:8010/mcp"
    }
  }
}
```

## Architecture

```
gnosis-vault/          # Plain .md files (source of truth)
  00-inbox/
  10-zettelkasten/
  20-projects/
  ...

backend/               # FastAPI + MCP server (port 8010)
  gnosis/
    config.py          # Pydantic settings
    database.py        # SQLAlchemy async engine
    models/            # ORM models
    schemas/           # Pydantic schemas
    routers/           # API endpoints
    services/
      markdown_parser  # Frontmatter + WikiLink extraction
      vault_sync       # Watchdog filesystem watcher
      embeddings       # fastembed dense + ColBERT
      vector_store     # Qdrant collection management
      hybrid_search    # BM25 + dense → RRF → ColBERT
      llm_provider     # Multi-provider with fallback
      graph_rag        # LightRAG integration
      document_parser  # PDF/DOCX/PPTX/image OCR
    core/
      auth             # JWT + bcrypt
      events           # FastAPI lifespan
      exceptions       # Custom error types
  alembic/             # DB migrations

frontend/              # Vite + React + TypeScript (port 3010)
  src/
    components/        # Layout, Sidebar, NoteEditor, GraphCanvas, AIChat
    pages/             # All route pages
    services/          # api.ts (typed fetch)
    store/             # Zustand global state
    types/             # TypeScript domain types
```

## Development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head
uvicorn gnosis.main:app --reload --port 8010
```

### Frontend

```bash
cd frontend
npm install
npm run dev   # starts at http://localhost:3010
```

### Tests

```bash
cd backend
pytest tests/ -v --cov=gnosis
```

## Note Types

| Type | Folder | Purpose |
|------|--------|---------|
| `fleeting` | 00-inbox | Quick captures, process daily |
| `permanent` | 10-zettelkasten | Atomic concepts, distilled insights |
| `project` | 20-projects | Active project notes |
| `literature` | 70-sources | Reading notes, web clips |
| `journal` | 60-journals | Daily notes |
| `map` | 80-meta | Maps of Content (MOC) |
| `reference` | 40-resources | Reference material |

## License

MIT — see [LICENSE](LICENSE)
