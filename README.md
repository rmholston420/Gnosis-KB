# Gnosis Knowledge Base

> A sovereign, Linux-native, AI-augmented personal knowledge base.

Gnosis unifies Zettelkasten methodology, PARA organization, and cutting-edge knowledge graph retrieval into a single self-hosted Docker stack. Every note is a plain `.md` file on your filesystem. The AI layer (LightRAG + Qdrant hybrid search) is purely local via Ollama — no data leaves your machine.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GNOSIS STACK                             │
│                                                                 │
│  React/TS (Vite 6) ◄──► FastAPI Backend (port 8010)            │
│  port 5173                                                      │
│                          Notes | Search | Graph | AI | MCP      │
│                                │         │                      │
│                         PostgreSQL 16   Qdrant 1.13             │
│                         port 5432       port 6333               │
│                                                                 │
│  ~/gnosis-vault/  (plain Markdown — the source of truth)        │
│  Watched by filesystem monitor (watchdog)                       │
└─────────────────────────────────────────────────────────────────┘
```

## Services

| Service | Technology | Port |
|---|---|---|
| `gnosis-api` | Python 3.12 + FastAPI | 8010 |
| `gnosis-mcp` | FastAPI-MCP (auto-mount) | 8011 |
| `gnosis-ui` | React + TypeScript + Vite 6 | 5173 |
| `gnosis-db` | PostgreSQL 16 | 5432 |
| `gnosis-vector` | Qdrant 1.13 | 6333 |
| `gnosis-ollama` | Ollama (optional) | 11434 |

## Quick Start

```bash
# 1. Clone
git clone https://github.com/rmholston420/Gnosis-KB.git
cd Gnosis-KB

# 2. Copy and edit environment
cp .env.example .env
# Edit .env: set SECRET_KEY, VAULT_PATH, optional LLM keys

# 3. Start infrastructure + API + UI
docker compose up -d

# 4. (Optional) Start with local Ollama GPU support
docker compose --profile local-ai up -d

# 5. Pull Ollama models (if using local AI)
docker exec gnosis-ollama ollama pull qwen2.5:14b
docker exec gnosis-ollama ollama pull nomic-embed-text

# 6. Open the app
open http://localhost:5173

# 7. API docs
open http://localhost:8010/docs

# 8. MCP server (for Claude Code / OpenHands)
claude mcp add gnosis http://localhost:8011/mcp
```

## Vault Directory Structure

```
~/gnosis-vault/
├── 00-inbox/          # Raw fleeting notes
├── 10-zettelkasten/   # Atomic permanent notes
├── 20-projects/       # Active projects
├── 30-areas/          # Ongoing responsibilities
├── 40-resources/      # Reference material
├── 50-archive/        # Inactive material
├── 60-journals/       # Daily / weekly notes
├── 70-sources/        # Literature notes
└── 80-meta/           # Templates, MOCs, system notes
```

## Development

See [DEVELOPMENT.md](DEVELOPMENT.md) for detailed setup instructions.

## License

MIT
