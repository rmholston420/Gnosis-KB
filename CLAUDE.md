# Gnosis KB — AI Agent Context

This file is the entry point for AI coding agents (Claude Code, OpenHands, Cursor) working on this codebase.

## Project Identity

- **Name**: Gnosis Knowledge Base
- **Owner**: rmholston420 (Retired Systems Scientist / Tibetan Buddhist Lama)
- **Purpose**: Sovereign, Linux-native, AI-augmented personal knowledge base
- **Stack**: FastAPI (Python 3.12) + React/TypeScript (Vite 6) + PostgreSQL 16 + Qdrant 1.13 + LightRAG
- **Philosophy**: Plain Markdown files are the source of truth. DB + Qdrant are derived caches. Zero vendor lock-in.

## Spec Document

The canonical build spec is in the Gnosis-KB Space as `Gnosis-Knowledge-Base-Build-Spec.md`. Always treat it as the single source of truth.

## Directory Layout

```
Gnosis-KB/
├── backend/           # FastAPI app (gnosis Python package)
│   ├── gnosis/        # Main application package
│   │   ├── main.py    # FastAPI app factory + MCP mount
│   │   ├── config.py  # pydantic-settings config
│   │   ├── database.py
│   │   ├── models/    # SQLAlchemy ORM models
│   │   ├── schemas/   # Pydantic request/response schemas
│   │   ├── routers/   # FastAPI route handlers
│   │   ├── services/  # Business logic
│   │   └── core/      # Auth, events, exceptions
│   ├── tests/
│   ├── alembic/
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/          # React + Vite app
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── vault/             # Default dev vault (gitignored content)
├── docker-compose.yml
├── .env.example
├── .github/workflows/ci.yml
├── DEVELOPMENT.md
└── CLAUDE.md          # This file
```

## Build Slices

| Slice | Phase | Status |
|---|---|---|
| 1 | Scaffold + Docker + Config | ✅ Complete |
| 2 | DB Models + Migrations + Auth | 🔄 In Progress |
| 3 | Vault Sync + Notes CRUD | Pending |
| 4 | Hybrid Search (Qdrant) | Pending |
| 5 | Graph Router + NetworkX | Pending |
| 6 | AI / LightRAG / LLM Provider | Pending |
| 7 | Document Ingest Pipeline | Pending |
| 8 | MCP Server | Pending |
| 9 | Frontend (React/Vite) | Pending |
| 10 | CI/CD + Polish | Pending |

## Key Architectural Decisions

1. **Vault watcher** (`watchdog`) syncs filesystem → PostgreSQL + Qdrant. It is a background asyncio task started in FastAPI lifespan.
2. **MCP exposure**: `fastapi-mcp` auto-exposes all FastAPI routes as MCP tools. Mounts at `/mcp` on port 8011.
3. **Hybrid search**: Qdrant three-vector collection: `dense` (BAAI/bge-base-en-v1.5, 768-dim) + `sparse` (BM25/IDF) + `colbert` (128-dim, multivector reranking). Fused with RRF.
4. **LightRAG**: Dual-level graph-RAG for multi-hop knowledge queries. Uses Ollama `qwen2.5:14b` + `nomic-embed-text`.
5. **Auth**: JWT via `python-jose`. No auth on MCP endpoints (localhost only).
6. **Soft deletes**: Notes are never hard-deleted from DB. `is_deleted=True` flag. Vault file preserved.
7. **Wikilinks**: `[[Title]]` syntax. Extracted by regex, stored in `links` table. Bidirectional.

## Environment Variables

All config in `backend/gnosis/config.py` via pydantic-settings. Copy `.env.example` → `.env`.

## Running Tests

```bash
cd backend
pip install -e ".[dev]"
pytest --cov=gnosis --cov-report=term-missing
```

## Coding Standards

- Python: ruff for linting, mypy for types, Google-style docstrings, no bare `Any`
- TypeScript: strict mode, no `any`, JSDoc on all functions
- Every router function must have at least one test
- 85% minimum coverage on `gnosis/services/` and `gnosis/routers/`
