# Gnosis: Advanced Linux-Native Knowledge Base — Complete Autonomous Build Spec

> **Purpose of this document**: A self-contained, authoritative application specification designed to be fed verbatim into an AI coding assistant (OpenHands, Claude Code, Cursor, or equivalent) for fully autonomous implementation. Every architectural decision is justified, every dependency pinned, and every interface defined. The AI agent should read this document once and produce a working, tested, containerized application without requiring clarifying questions.

***

## Executive Summary

**Gnosis** is a sovereign, Linux-native, AI-augmented personal knowledge base that synthesizes the best design principles from Zettelkasten methodology, PARA organization, and cutting-edge knowledge graph retrieval. It is a full-stack web application—not a desktop Electron app—built on the same FastAPI/React/PostgreSQL/Docker stack already in use across the Rigpa-v2/v3 and Neurolink-v1 projects. The result is a tool that survives decades (plain-text source of truth), scales to millions of notes (Qdrant vector database), reasons across relationships (LightRAG dual-level graph-RAG), and integrates natively into the AI-agent workflow (MCP server exposed via FastAPI-MCP).

**Key innovation over existing tools**: Gnosis unifies what currently requires four separate applications (Obsidian + Dataview + LLM Wiki + AnythingLLM) into a single self-hosted Docker stack where every component is owned, every datum is local, and the full system exposes an MCP interface to AI coding agents.

***

## Part I: Design Philosophy & Requirements

### Non-Negotiable Architectural Principles

These principles are drawn from the attached design guide and must govern every implementation decision:

1. **Plain Markdown files are the source of truth** — All notes stored as `.md` files on a watched filesystem directory. The PostgreSQL database and Qdrant vector store are *derived caches* of that filesystem. Deleting the database never destroys knowledge.
2. **No vendor lock-in** — Every data format is open and human-readable without software. YAML frontmatter, Markdown body, wikilinks as `[[Title]]` text strings.
3. **Local-first AI** — All LLM inference runs via Ollama. No API key required for core functionality. OpenRouter/Groq/OpenAI are optional enhancement channels.
4. **Atomic notes** — One idea per permanent note. Enforced by UI guidance and AI critique, not hard constraints.
5. **Links over folders** — Bidirectional wikilinks (`[[Title]]`) are the primary navigation structure. The folder hierarchy is PARA-based but notes are found via graph traversal, not tree navigation.
6. **Sovereignty** — Zero data leaves the host machine unless the user explicitly configures an external LLM provider.

### Information Architecture

Following the eight principles of knowledge base IA, the directory structure is:

```
~/gnosis-vault/
├── 00-inbox/          # Raw fleeting notes — capture without friction
├── 10-zettelkasten/   # Atomic permanent notes (the core intelligence layer)
├── 20-projects/       # Active projects with start/end date and outcome
├── 30-areas/          # Ongoing responsibilities (domains of life/work)
├── 40-resources/      # Reference material organized by topic domain
├── 50-archive/        # Inactive material, never deleted
├── 60-journals/       # Daily / weekly / periodic notes
├── 70-sources/        # Literature notes — one note per source, cited
└── 80-meta/           # Templates, Maps of Content (MOCs), system notes
```

**Note types and their frontmatter schema**:

```yaml
# Permanent note (10-zettelkasten/)
---
id: "20260619-143022"          # Unique timestamp ID
title: "Artifact detection in EEG signals"
type: permanent                # fleeting | literature | permanent | project | area | resource | journal | moc
status: evergreen              # draft | in-progress | evergreen
tags: [eeg, signal-processing, neurolink]
created: 2026-06-19T14:30:22
modified: 2026-06-19T14:30:22
source: ""                     # URL or citation key for literature notes
links: []                      # Explicit outgoing wikilinks (auto-populated)
last_reviewed: 2026-06-19
---
```

***

## Part II: System Architecture

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        GNOSIS STACK                             │
│                                                                 │
│  ┌──────────────┐    ┌──────────────────────────────────────┐  │
│  │  React/TS    │◄──►│         FastAPI Backend               │  │
│  │  Frontend    │    │  (gnosis-api : port 8010)             │  │
│  │  (Vite 6)    │    │                                       │  │
│  │  port 5173   │    │  ┌──────────┐  ┌────────────────┐   │  │
│  └──────────────┘    │  │  Notes   │  │  AI / RAG      │   │  │
│                      │  │  Router  │  │  Router        │   │  │
│  ┌──────────────┐    │  └──────────┘  └────────────────┘   │  │
│  │   AI Agent   │    │  ┌──────────┐  ┌────────────────┐   │  │
│  │  (Claude/    │◄──►│  │  Graph   │  │  MCP Server    │   │  │
│  │  OpenHands)  │    │  │  Router  │  │  (port 8011)   │   │  │
│  └──────────────┘    │  └──────────┘  └────────────────┘   │  │
│         │            └──────────────────────────────────────┘  │
│         │                    │              │                   │
│         │            ┌───────┘    ┌─────────┘                  │
│         ▼            ▼            ▼                             │
│  ┌─────────┐  ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │
│  │   MCP   │  │PostgreSQL│ │  Qdrant  │ │ Ollama (local)   │  │
│  │  port   │  │  :5432   │ │  :6333   │ │  :11434          │  │
│  │  8011   │  └──────────┘ └──────────┘ │  (or ext. API)   │  │
│  └─────────┘                            └──────────────────┘  │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │         ~/gnosis-vault/ (plain Markdown files)          │   │
│  │         Watched by filesystem monitor (watchdog)        │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### Service Inventory

| Service | Image / Technology | Port | Purpose |
|---|---|---|---|
| `gnosis-api` | Python 3.12 + FastAPI + uvicorn | 8010 | Backend REST API + WebSocket |
| `gnosis-mcp` | FastAPI-MCP auto-mount | 8011 | MCP server for AI agents |
| `gnosis-ui` | React + TypeScript + Vite 6 | 5173 (dev) / 80 (prod) | Web frontend |
| `gnosis-db` | PostgreSQL 16 | 5432 | Metadata, graph edges, session state |
| `gnosis-vector` | Qdrant 1.13 | 6333 / 6334 | Vector embeddings + hybrid search |
| `gnosis-ollama` | Ollama (optional) | 11434 | Local LLM + embedding inference |
| `gnosis-watcher` | Python watchdog subprocess | — | Filesystem sync → DB + Qdrant |

***

## Part III: Technology Stack (Pinned Versions)

### Backend

```toml
# pyproject.toml
[project]
name = "gnosis-api"
version = "1.0.0"
requires-python = ">=3.12"

dependencies = [
    # Web framework
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.30.0",
    "fastapi-mcp>=0.3.0",          # Zero-config MCP server from FastAPI routes

    # Database
    "sqlalchemy>=2.0.30",
    "alembic>=1.13.0",
    "asyncpg>=0.29.0",             # Async PostgreSQL driver
    "psycopg2-binary>=2.9.9",

    # Vector database
    "qdrant-client>=1.9.0",        # Qdrant Python client
    "fastembed>=0.3.0",            # Qdrant's own embedding lib (no Torch needed)

    # AI / LLM
    "lightrag-hku>=1.3.0",         # LightRAG dual-level graph-RAG
    "ollama>=0.2.0",               # Ollama Python client
    "openai>=1.40.0",              # OpenAI-compatible client (Groq, OpenRouter)

    # Document parsing
    "python-frontmatter>=1.1.0",   # YAML frontmatter parse/write
    "mistune>=3.0.2",              # Markdown → HTML/AST
    "pymupdf>=1.24.0",             # PDF parsing (PyMuPDF)
    "python-docx>=1.1.0",          # DOCX parsing
    "python-pptx>=0.6.23",         # PPTX parsing
    "openpyxl>=3.1.2",             # XLSX parsing
    "pytesseract>=0.3.10",         # OCR (requires tesseract-ocr system package)
    "Pillow>=10.3.0",              # Image processing

    # Filesystem watching
    "watchdog>=4.0.0",             # Vault directory monitor

    # Utilities
    "pydantic>=2.7.0",
    "pydantic-settings>=2.3.0",
    "python-jose[cryptography]>=3.3.0",  # JWT auth
    "passlib[bcrypt]>=1.7.4",
    "python-multipart>=0.0.9",
    "httpx>=0.27.0",
    "anyio>=4.4.0",
    "python-slugify>=8.0.4",
    "networkx>=3.3",               # In-memory graph analysis
    "rank_bm25>=0.2.2",            # BM25 for hybrid search fallback
]

[project.optional-dependencies]
dev = [
    "pytest>=8.2.0",
    "pytest-asyncio>=0.23.7",
    "pytest-cov>=5.0.0",
    "httpx>=0.27.0",               # TestClient
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]
```

### Frontend

```json
// package.json key dependencies
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "typescript": "^5.5.0",
    "@tanstack/react-query": "^5.45.0",
    "axios": "^1.7.0",
    "react-router-dom": "^6.24.0",
    "@tiptap/react": "^2.5.0",
    "@tiptap/starter-kit": "^2.5.0",
    "@tiptap/extension-link": "^2.5.0",
    "@tiptap/extension-mention": "^2.5.0",    // WikiLink autocomplete
    "@tiptap/extension-code-block-lowlight": "^2.5.0",
    "react-force-graph-2d": "^1.25.0",        // D3 force graph
    "three": "^0.165.0",                      // 3D graph option
    "@react-three/fiber": "^8.16.0",
    "lucide-react": "^0.400.0",
    "tailwindcss": "^3.4.0",
    "@radix-ui/react-*": "^1.x.x",           // Headless UI primitives
    "zustand": "^4.5.0",                      // State management
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "rehype-highlight": "^7.0.0",
    "date-fns": "^3.6.0",
    "fuse.js": "^7.0.0",                      // Client-side fuzzy search
    "cmdk": "^1.0.0"                          // Command palette (Cmd+K)
  },
  "devDependencies": {
    "vite": "^6.0.0",
    "@vitejs/plugin-react": "^4.3.0",
    "playwright": "^1.44.0",
    "@playwright/test": "^1.44.0",
    "vitest": "^1.6.0",
    "@testing-library/react": "^16.0.0"
  }
}
```

### Infrastructure

```yaml
# docker-compose.yml (complete)
version: "3.9"

services:
  gnosis-db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: gnosis
      POSTGRES_USER: gnosis
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-gnosis_dev}
    volumes:
      - gnosis-db-data:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U gnosis"]
      interval: 10s
      timeout: 5s
      retries: 5

  gnosis-vector:
    image: qdrant/qdrant:v1.13.0
    volumes:
      - gnosis-qdrant-data:/qdrant/storage
    ports:
      - "6333:6333"
      - "6334:6334"
    environment:
      QDRANT__SERVICE__GRPC_PORT: "6334"

  gnosis-ollama:
    image: ollama/ollama:latest
    volumes:
      - gnosis-ollama-models:/root/.ollama
    ports:
      - "11434:11434"
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: all
              capabilities: [gpu]
    profiles:
      - local-ai                   # Only runs if --profile local-ai

  gnosis-api:
    build:
      context: ./backend
      dockerfile: Dockerfile
    environment:
      DATABASE_URL: postgresql+asyncpg://gnosis:${POSTGRES_PASSWORD:-gnosis_dev}@gnosis-db:5432/gnosis
      QDRANT_URL: http://gnosis-vector:6333
      VAULT_PATH: /vault
      OLLAMA_BASE_URL: ${OLLAMA_BASE_URL:-http://gnosis-ollama:11434}
      SECRET_KEY: ${SECRET_KEY:-change_in_production_immediately}
      OPENAI_API_KEY: ${OPENAI_API_KEY:-}
      GROQ_API_KEY: ${GROQ_API_KEY:-}
      LOG_LEVEL: ${LOG_LEVEL:-info}
    volumes:
      - ${VAULT_PATH:-./vault}:/vault
      - ./backend:/app                  # Hot reload in dev
    ports:
      - "8010:8010"
      - "8011:8011"
    depends_on:
      gnosis-db:
        condition: service_healthy
      gnosis-vector:
        condition: service_started
    command: uvicorn gnosis.main:app --host 0.0.0.0 --port 8010 --reload

  gnosis-ui:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    environment:
      VITE_API_BASE_URL: ${VITE_API_BASE_URL:-http://localhost:8010}
    ports:
      - "5173:5173"
    volumes:
      - ./frontend:/app
      - /app/node_modules
    depends_on:
      - gnosis-api
    command: npm run dev -- --host

volumes:
  gnosis-db-data:
  gnosis-qdrant-data:
  gnosis-ollama-models:
```

***

## Part IV: Backend Architecture

### Module Structure

```
backend/
├── gnosis/
│   ├── __init__.py
│   ├── main.py                    # FastAPI app factory + MCP mount
│   ├── config.py                  # Settings via pydantic-settings
│   ├── database.py                # Async SQLAlchemy engine + session
│   ├── models/                    # SQLAlchemy ORM models
│   │   ├── note.py
│   │   ├── link.py
│   │   ├── tag.py
│   │   ├── attachment.py
│   │   └── user.py
│   ├── schemas/                   # Pydantic request/response schemas
│   │   ├── note.py
│   │   ├── search.py
│   │   ├── graph.py
│   │   └── ai.py
│   ├── routers/                   # FastAPI route handlers
│   │   ├── notes.py               # CRUD for notes
│   │   ├── search.py              # Hybrid search endpoint
│   │   ├── graph.py               # Graph traversal endpoints
│   │   ├── ai.py                  # AI generation, summarize, chat
│   │   ├── ingest.py              # Document upload + parse
│   │   ├── tags.py
│   │   └── health.py
│   ├── services/
│   │   ├── vault_sync.py          # Filesystem watcher → DB sync
│   │   ├── markdown_parser.py     # Parse .md frontmatter + wikilinks
│   │   ├── vector_store.py        # Qdrant collection management
│   │   ├── hybrid_search.py       # BM25 + vector RRF fusion
│   │   ├── graph_rag.py           # LightRAG integration
│   │   ├── llm_provider.py        # Multi-provider LLM (Ollama/Groq/OpenAI)
│   │   ├── document_parser.py     # PDF/DOCX/PPTX/XLSX/OCR ingestion
│   │   └── embeddings.py          # Embedding generation via fastembed
│   ├── core/
│   │   ├── auth.py                # JWT authentication
│   │   ├── events.py              # Startup/shutdown lifespan events
│   │   └── exceptions.py
│   └── alembic/                   # Database migrations
│       ├── env.py
│       └── versions/
├── tests/
│   ├── conftest.py
│   ├── test_notes.py
│   ├── test_search.py
│   ├── test_graph.py
│   ├── test_ai.py
│   └── test_vault_sync.py
├── requirements.txt
├── pyproject.toml
└── Dockerfile
```

### Database Schema (SQLAlchemy Models)

```python
# gnosis/models/note.py
class Note(Base):
    __tablename__ = "notes"

    id: Mapped[str] = mapped_column(String(20), primary_key=True)  # timestamp ID
    title: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(500), unique=True, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    body_html: Mapped[str] = mapped_column(Text, nullable=False, default="")
    note_type: Mapped[str] = mapped_column(String(50), default="permanent")
    status: Mapped[str] = mapped_column(String(50), default="draft")
    vault_path: Mapped[str] = mapped_column(String(1000), unique=True)  # Relative path in vault
    folder: Mapped[str] = mapped_column(String(100), index=True)  # 00-inbox, 10-zettel...
    source_url: Mapped[Optional[str]] = mapped_column(Text)
    word_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    modified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    last_reviewed: Mapped[Optional[date]] = mapped_column(Date)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    vector_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    graph_indexed: Mapped[bool] = mapped_column(Boolean, default=False)
    frontmatter: Mapped[dict] = mapped_column(JSONB, default=dict)  # Raw frontmatter dict

    # Relationships
    outgoing_links: Mapped[List["Link"]] = relationship("Link", foreign_keys="Link.source_id", back_populates="source")
    incoming_links: Mapped[List["Link"]] = relationship("Link", foreign_keys="Link.target_id", back_populates="target")
    tags: Mapped[List["Tag"]] = relationship("Tag", secondary="note_tags", back_populates="notes")
    attachments: Mapped[List["Attachment"]] = relationship("Attachment", back_populates="note")

# gnosis/models/link.py
class Link(Base):
    __tablename__ = "links"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("notes.id", ondelete="CASCADE"), index=True)
    link_text: Mapped[str] = mapped_column(String(500))  # The [[Link Text]] as written
    context: Mapped[Optional[str]] = mapped_column(Text)  # Surrounding paragraph for context
    link_type: Mapped[str] = mapped_column(String(50), default="wikilink")  # wikilink | mention | citation

    source: Mapped["Note"] = relationship("Note", foreign_keys=[source_id])
    target: Mapped["Note"] = relationship("Note", foreign_keys=[target_id])
```

### Vault Sync Service

The filesystem watcher is the backbone of Gnosis's plain-text sovereignty. It runs as a background task started in FastAPI's lifespan context:

```python
# gnosis/services/vault_sync.py
"""
Watches ~/gnosis-vault/ for file changes.
On create/modify: parse frontmatter + body, upsert to DB, queue for vector indexing.
On delete: mark as is_deleted=True in DB (never hard-delete).
Maintains bidirectional link table from parsed [[wikilinks]].
"""

import re
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

WIKILINK_PATTERN = re.compile(r'\[\[([^\[\]|]+)(?:\|[^\[\]]+)?\]\]')
FRONTMATTER_PATTERN = re.compile(r'^---\n(.*?)\n---\n', re.DOTALL)

class VaultEventHandler(FileSystemEventHandler):
    async def on_modified(self, event): ...
    async def on_created(self, event): ...
    async def on_deleted(self, event): ...
    async def _sync_note(self, path: Path): ...
    async def _extract_wikilinks(self, body: str) -> list[str]: ...
    async def _rebuild_links(self, note: Note, wikilinks: list[str]): ...
```

### API Endpoints

All endpoints are documented via OpenAPI and auto-exposed as MCP tools via `fastapi-mcp`. The MCP server mounts at `/mcp` (port 8011).[^1][^2]

#### Notes Router (`/api/v1/notes`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | List notes with filters (folder, type, status, tags, search) |
| `POST` | `/` | Create note (writes .md to vault, triggers sync) |
| `GET` | `/{note_id}` | Get note by ID with backlinks |
| `PUT` | `/{note_id}` | Update note (writes to vault file) |
| `DELETE` | `/{note_id}` | Soft delete (marks is_deleted; keeps vault file) |
| `GET` | `/{note_id}/backlinks` | Get all notes linking to this note |
| `GET` | `/{note_id}/outlinks` | Get all notes this note links to |
| `GET` | `/orphans` | Notes with zero incoming + outgoing links |
| `GET` | `/daily` | Get or create today's daily note |
| `POST` | `/from-template/{template_slug}` | Create note from template |

#### Search Router (`/api/v1/search`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Hybrid search: BM25 + vector RRF fusion [^3] |
| `GET` | `/semantic` | Pure semantic vector search |
| `GET` | `/fulltext` | Pure BM25 full-text search |
| `GET` | `/tags` | Search by tags |
| `GET` | `/similar/{note_id}` | Find semantically similar notes |

#### Graph Router (`/api/v1/graph`)

| Method | Path | Description |
|---|---|---|
| `GET` | `/` | Full graph (nodes + edges) for visualization |
| `GET` | `/neighborhood/{note_id}` | Ego-graph: note + 1-hop neighbors |
| `GET` | `/path/{from_id}/{to_id}` | Shortest path between two notes |
| `GET` | `/clusters` | Community detection (NetworkX Louvain) |
| `GET` | `/stats` | Graph statistics: density, avg degree, orphans |

#### AI Router (`/api/v1/ai`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/chat` | RAG-powered chat over the vault (LightRAG) [^4] |
| `POST` | `/summarize/{note_id}` | AI summary of a note |
| `POST` | `/suggest-links/{note_id}` | Suggest wikilinks for a note |
| `POST` | `/suggest-tags/{note_id}` | Suggest tags for a note |
| `POST` | `/extract-entities` | Extract entities from text → graph nodes |
| `POST` | `/critique/{note_id}` | Zettelkasten critique (is this atomic? does it need links?) |
| `GET` | `/orphan-audit` | AI-powered orphan audit: suggest connections for isolated notes |
| `POST` | `/daily-review` | Generate daily review from inbox notes |
| `GET` | `/stream/chat` | Server-Sent Events streaming chat endpoint |

#### Ingest Router (`/api/v1/ingest`)

| Method | Path | Description |
|---|---|---|
| `POST` | `/file` | Upload and parse PDF/DOCX/PPTX/XLSX/image → Markdown note |
| `POST` | `/url` | Scrape URL → Markdown literature note |
| `POST` | `/batch` | Batch import a zip of Markdown files |

### Hybrid Search Implementation

Gnosis implements three-vector hybrid search modeled on Qdrant best practices:[^5][^6]

```python
# gnosis/services/hybrid_search.py
"""
Qdrant collection: "gnosis_notes"
Three named vectors per point:
  - "dense":   BAAI/bge-base-en-v1.5 (768-dim) via fastembed
  - "sparse":  BM25 (Qdrant/bm25 modifier=IDF)
  - "colbert": colbertv2.0 (128-dim, multivector) for reranking

Search pipeline:
  Stage 1: Prefetch dense (top-50) + prefetch sparse (top-50)
  Stage 2: Fuse with RRF (Reciprocal Rank Fusion)
  Stage 3: Rerank with ColBERT MAX_SIM on top-20
  Returns: top-10 with scores + payload
"""

from qdrant_client import QdrantClient, models

COLLECTION_NAME = "gnosis_notes"

async def create_collection(client: QdrantClient) -> None:
    client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config={
            "dense": models.VectorParams(
                size=768,
                distance=models.Distance.COSINE,
            ),
            "colbert": models.VectorParams(
                size=128,
                distance=models.Distance.COSINE,
                multivector_config=models.MultiVectorConfig(
                    comparator=models.MultiVectorComparator.MAX_SIM
                ),
                hnsw_config=models.HnswConfigDiff(m=0),  # reranking only
            ),
        },
        sparse_vectors_config={
            "sparse": models.SparseVectorParams(
                modifier=models.Modifier.IDF
            )
        },
    )

async def hybrid_search(client: QdrantClient, query: str, limit: int = 10):
    return client.query_points(
        collection_name=COLLECTION_NAME,
        prefetch=[
            models.Prefetch(
                query=models.Document(text=query, model="Qdrant/bm25"),
                using="sparse",
                limit=50,
            ),
            models.Prefetch(
                query=models.Document(text=query, model="BAAI/bge-base-en-v1.5"),
                using="dense",
                limit=50,
            ),
        ],
        query=models.FusionQuery(fusion=models.Fusion.RRF),
        limit=limit,
    )
```

### LightRAG Integration

LightRAG provides dual-level graph-aware retrieval that far outperforms flat vector RAG for multi-hop questions about interconnected knowledge. It automatically extracts entities and relationships from notes during ingestion and builds a knowledge graph on top of the vector index:[^4][^7]

```python
# gnosis/services/graph_rag.py
"""
LightRAG setup with local Ollama for both LLM and embedding.
Working directory: ./lightrag-data/  (persists graph + vector cache)
Three query modes:
  - local:   specific entity lookups ("what does note X say about Y?")
  - global:  thematic synthesis ("what are recurring themes in my EEG notes?")
  - hybrid:  combines both (default for chat endpoint)

Entity types tuned to knowledge base domain:
  - concept, person, organization, project, tool, technique, insight
"""
from lightrag import LightRAG, QueryParam
from lightrag.llm.ollama import ollama_model_complete, ollama_embed

rag = LightRAG(
    working_dir="./lightrag-data",
    llm_model_func=ollama_model_complete,
    llm_model_name="qwen2.5:14b",          # Recommended: 14b+ for quality KG extraction
    embedding_func=ollama_embed,
    embedding_model="nomic-embed-text",     # nomic-embed-text via Ollama [cite:file:1]
    entity_types=["concept", "person", "project", "tool", "technique", "insight", "question"],
)

async def ingest_note(note: Note) -> None:
    """Called when a note is created or updated."""
    await rag.ainsert(note.title + "\n\n" + note.body)

async def query_vault(question: str, mode: str = "hybrid") -> str:
    return await rag.aquery(question, param=QueryParam(mode=mode))
```

### MCP Server Exposure

Using `fastapi-mcp`, the entire REST API is automatically exposed as an MCP server with zero additional code. AI agents (Claude Code, OpenHands, Cursor) can call all FastAPI routes as MCP tools:[^2][^1]

```python
# gnosis/main.py
from fastapi import FastAPI
from fastapi_mcp import FastApiMCP

app = FastAPI(title="Gnosis Knowledge Base API", version="1.0.0")

# ... register all routers ...

mcp = FastApiMCP(
    app,
    name="gnosis-kb",
    description="Gnosis Knowledge Base MCP server. Tools for reading, writing, searching, and reasoning over a personal knowledge graph.",
    base_url="http://localhost:8010",
)
mcp.mount()  # Mounts at /mcp, runs on same process
```

This means Claude Code (or any MCP-compatible agent) can call `gnosis-kb/search`, `gnosis-kb/ai/chat`, `gnosis-kb/graph/neighborhood`, etc. directly. The knowledge base becomes the **persistent memory layer for autonomous AI agents**.

***

## Part V: Frontend Architecture

### Module Structure

```
frontend/src/
├── main.tsx
├── App.tsx
├── api/                           # Axios API client (auto-generated from OpenAPI)
│   ├── client.ts
│   ├── notes.ts
│   ├── search.ts
│   ├── graph.ts
│   └── ai.ts
├── components/
│   ├── editor/
│   │   ├── NoteEditor.tsx         # TipTap rich text editor with WikiLink support
│   │   ├── WikiLinkExtension.ts   # Custom TipTap extension: [[Title]] → mention
│   │   ├── FrontmatterPanel.tsx   # Sidebar: type, status, tags, dates
│   │   └── BacklinksPanel.tsx     # Live backlinks list
│   ├── graph/
│   │   ├── GraphView2D.tsx        # react-force-graph-2d
│   │   ├── GraphView3D.tsx        # react-force-graph-3d (optional)
│   │   ├── GraphControls.tsx      # Zoom, filter, cluster toggle
│   │   └── NodeDetailOverlay.tsx  # Click node → show note preview
│   ├── search/
│   │   ├── CommandPalette.tsx     # Cmd+K global search (cmdk)
│   │   ├── SearchResults.tsx      # Highlighted hybrid search results
│   │   └── SemanticSearch.tsx     # Vector search UI
│   ├── ai/
│   │   ├── AiChat.tsx             # Streaming RAG chat panel
│   │   ├── AiSidebar.tsx          # Summarize, suggest links, critique
│   │   └── LinkSuggestions.tsx    # AI-suggested wikilinks
│   ├── sidebar/
│   │   ├── VaultTree.tsx          # Folder tree (PARA buckets)
│   │   ├── DailyNoteWidget.tsx
│   │   └── TagCloud.tsx
│   ├── layout/
│   │   ├── MainLayout.tsx
│   │   ├── SplitPane.tsx          # Resizable editor/preview split
│   │   └── ThemeToggle.tsx
│   └── shared/
│       ├── MarkdownPreview.tsx    # Rendered Markdown with wikilink navigation
│       ├── TagBadge.tsx
│       └── NoteCard.tsx
├── pages/
│   ├── VaultPage.tsx              # Main vault browser
│   ├── EditorPage.tsx             # Full-screen note editor
│   ├── GraphPage.tsx              # Full-screen knowledge graph
│   ├── SearchPage.tsx             # Search results page
│   ├── InboxPage.tsx              # Inbox review workflow
│   ├── DailyNotePage.tsx          # Today's daily note
│   ├── AiChatPage.tsx             # Full-screen AI chat
│   └── SettingsPage.tsx           # LLM provider config, vault path
├── stores/
│   ├── vaultStore.ts              # Zustand: vault state
│   ├── editorStore.ts             # Active note, dirty state
│   ├── graphStore.ts              # Graph data + filters
│   └── aiStore.ts                 # Chat history, provider config
├── hooks/
│   ├── useNotes.ts
│   ├── useSearch.ts
│   ├── useGraph.ts
│   ├── useAI.ts
│   └── useWebSocket.ts            # Real-time updates from vault watcher
└── lib/
    ├── markdownUtils.ts           # Wikilink parsing, frontmatter rendering
    ├── graphUtils.ts              # Graph data transforms for react-force-graph
    └── dateUtils.ts
```

### WikiLink Editor (TipTap Extension)

The WikiLink implementation follows the Obsidian convention: typing `[[` triggers an autocomplete dropdown showing matching note titles. Selecting a note inserts `[[Note Title]]` as a styled inline link. On render, wikilinks navigate to the linked note.

```typescript
// components/editor/WikiLinkExtension.ts
import { Mention } from "@tiptap/extension-mention";
import { fetchNotes } from "../../api/notes";

export const WikiLinkExtension = Mention.extend({
  name: "wikilink",
}).configure({
  HTMLAttributes: { class: "wikilink" },
  renderLabel({ node }) {
    return `[[${node.attrs.label ?? node.attrs.id}]]`;
  },
  suggestion: {
    char: "

### Graph Visualization

The graph view renders the vault as a force-directed network. Nodes are notes, edges are wikilinks. Node color encodes note type; node size encodes incoming link count (betweenness centrality)[^74]:

```typescript
// components/graph/GraphView2D.tsx
import ForceGraph2D from "react-force-graph-2d";

const NODE_COLORS = {
  permanent: "#3b82f6",     // blue
  fleeting: "#94a3b8",      // gray
  project: "#f59e0b",       // amber
  area: "#10b981",          // green
  resource: "#8b5cf6",      // violet
  journal: "#ec4899",       // pink
  moc: "#ef4444",           // red
};

export function GraphView2D({ data, onNodeClick }) {
  return (
    <ForceGraph2D
      graphData={data}
      nodeColor={node => NODE_COLORS[node.type] ?? "#6b7280"}
      nodeVal={node => Math.sqrt(node.incomingLinkCount + 1) * 3}
      linkWidth={link => link.type === "wikilink" ? 1 : 0.5}
      onNodeClick={onNodeClick}
      nodeLabel={node => node.title}
      linkDirectionalArrowLength={3}
      linkDirectionalArrowRelPos={1}
      enableNodeDrag={true}
      cooldownTicks={100}
    />
  );
}
```

---

## Part VI: Key Feature Specifications

### Feature 1: Quick Capture (Cmd+K → New Note)

- Global command palette (cmdk library) opens from anywhere
- First option: "New note in inbox" → creates `00-inbox/YYYY-MM-DD-HH-mm-ss.md`
- Pre-populated with frontmatter template
- Autosaves on every keystroke (500ms debounce) via WebSocket or polling
- Note appears in vault tree immediately via vault watcher

### Feature 2: Daily Note Workflow

- A Daily Note for today auto-creates at `/60-journals/YYYY-MM-DD.md` when accessed
- Template includes: date, mood tracker (1-5), priorities (3 items), capture section, end-of-day reflection
- Daily note links to any inbox notes created that day
- Weekly review template aggregates 7 daily notes

### Feature 3: Maps of Content (MOC) Generator

- User selects a topic/tag
- AI generates a MOC note: H2 sections by subtopic, each with wikilinks to relevant permanent notes
- Placed in `80-meta/`
- MOC notes rendered with special "hub" styling in the graph view

### Feature 4: Orphan Detection & Remediation

- Daily background job finds notes with `incoming_links = 0 AND outgoing_links = 0`
- For each orphan: AI suggests 3–5 existing notes to link, with explanation of why
- User accepts/rejects suggestions from an "Orphan Review" panel in UI
- Accepted links are written directly to the vault file

### Feature 5: AI Zettelkasten Critique

- User triggers critique on any permanent note
- Prompt: "Review this Zettelkasten note for: (1) atomicity — does it contain exactly one idea? (2) connectivity — does it have at least 3 outgoing links? (3) self-containedness — can it be understood without context? (4) insight density — does it capture 'why this matters'?"
- Response displayed inline with actionable suggestions

### Feature 6: Document Import Pipeline

Multi-format ingestion via the `/api/v1/ingest/file` endpoint:
1. Upload PDF / DOCX / PPTX / XLSX / image (PNG, JPG)
2. Parse to plain text (PyMuPDF / python-docx / Tesseract)
3. AI generates: title, summary, key terms, suggested folder
4. Creates a literature note in `70-sources/` with:
   - Extracted text as collapsed `<details>` block
   - AI summary as the note body
   - `source:` frontmatter with original filename + upload timestamp
   - Auto-suggested wikilinks to related existing notes

### Feature 7: Full-Vault AI Chat (LightRAG)

- Persistent chat interface backed by LightRAG hybrid query mode[^31]
- Three query modes selectable in UI: Local (specific facts), Global (themes/synthesis), Hybrid (default)
- Citations: every response cites the source note titles as wikilinks
- Chat history persisted in PostgreSQL per session
- Streaming via SSE (Server-Sent Events)

### Feature 8: Dataview-Style Query Dashboard

Inspired by Obsidian's Dataview plugin[cite:file:1], implement a query endpoint and UI panel:

```
# Example query syntax (custom, not Dataview)
FROM "10-zettelkasten"
WHERE status = "draft"
  AND tags CONTAINS "eeg"
  AND modified > 7d
SORT modified DESC
LIMIT 20
SELECT title, status, tags, modified
```

Frontend renders this as a live-updating table. Users save queries as named dashboards.

---

## Part VII: Testing Strategy

All tests follow the pytest + pytest-asyncio pattern established in Rigpa-v2/v3:

```
tests/
├── conftest.py              # Fixtures: test DB, mock vault, test Qdrant collection
├── unit/
│   ├── test_markdown_parser.py   # Wikilink extraction, frontmatter parsing
│   ├── test_vault_sync.py        # File create/modify/delete → DB sync
│   └── test_hybrid_search.py    # Search result ranking
├── integration/
│   ├── test_notes_api.py         # CRUD + vault file creation
│   ├── test_search_api.py        # Hybrid search results
│   ├── test_graph_api.py         # Graph traversal correctness
│   └── test_ai_api.py            # AI endpoints (with mocked Ollama)
└── e2e/
    └── test_workflow.py          # Playwright: create note → link → search → find
```

**Coverage target**: 85% minimum on `gnosis/services/` and `gnosis/routers/`.

**CI/CD** (GitHub Actions):
```yaml
# .github/workflows/ci.yml
- Ruff lint + mypy type check
- pytest --cov=gnosis --cov-report=xml
- Docker build verification
- Playwright E2E on build artifact
```

---

## Part VIII: Code to Cannibalize from GitHub

The following open-source repositories contain production-ready code that should be studied, adapted, and integrated rather than reinvented:

| Repository | What to Cannibalize | License |
|---|---|---|
| [NoahRolli/pallas](https://github.com/NoahRolli/pallas) | AI architecture (three-tier provider + auto-fallback), WikiLink TipTap extension, Three.js 3D sphere, AES-256-GCM encryption pattern, Docker Compose structure | MIT |
| [ancoleman/qdrant-rag-mcp](https://github.com/ancoleman/qdrant-rag-mcp) | Complete BM25 + vector RRF hybrid search implementation (`src/utils/hybrid_search.py`), Qdrant collection schema, MCP tool definitions | MIT |
| [fastapi/full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) | JWT auth, SQLModel patterns, Docker Compose, GitHub Actions CI, Traefik reverse proxy, Playwright E2E setup[^82] | MIT |
| [tadata-org/fastapi_mcp](https://github.com/tadata-org/fastapi_mcp) | Zero-config FastAPI → MCP server mounting pattern (2 lines of code)[^99] | MIT |
| [vasturiano/react-force-graph](https://github.com/vasturiano/react-force-graph) | react-force-graph-2d: force-directed graph component with WebGL acceleration[^74] | MIT |
| [RUC-NLPIR/FlashRAG](https://github.com/RUC-NLPIR/FlashRAG) | Modular RAG evaluation toolkit, chunking strategies, retrieval benchmarks[^27] | MIT |
| [ayyzenn/local-rag-ollama](https://github.com/ayyzenn/local-rag-ollama) | Complete local RAG pipeline with Ollama + ChromaDB + Python[^49] | MIT |

---

## Part IX: AI Agent Build Instructions

This section is written as direct instructions for the AI coding assistant executing this spec.

### Persona

You are a senior full-stack Python/TypeScript engineer specializing in knowledge management systems and AI-augmented applications. You write production-quality, type-safe, well-tested code. You never use `Any` types in TypeScript. You never use `any` type in Python without a `# type: ignore` comment explaining why.

### Build Order (Execute in Sequence)

**Phase 1 — Foundation (Backend)**
1. Scaffold project directory structure exactly as specified in Part IV
2. Implement `gnosis/config.py` using pydantic-settings; all config values from environment variables with sensible defaults
3. Implement `gnosis/database.py` with async SQLAlchemy engine
4. Implement all SQLAlchemy models in `gnosis/models/`
5. Generate and run initial Alembic migration
6. Implement `gnosis/core/auth.py` JWT authentication (copied from fastapi/full-stack-fastapi-template pattern)
7. Write `docker-compose.yml` exactly as specified
8. Write `backend/Dockerfile`: Python 3.12-slim, installs system deps (tesseract, libmagic), copies app, runs uvicorn
9. Verify `docker compose up gnosis-db gnosis-vector` starts cleanly

**Phase 2 — Notes CRUD**
1. Implement `gnosis/services/markdown_parser.py` with full wikilink extraction and frontmatter round-trip
2. Implement `gnosis/services/vault_sync.py` with watchdog FileSystemEventHandler
3. Implement `gnosis/routers/notes.py` with all endpoints specified in Part IV
4. Write tests for all note operations: create, read, update, delete, list, backlinks
5. Verify vault file is created/updated when API creates/updates a note

**Phase 3 — Search**
1. Implement `gnosis/services/embeddings.py` using fastembed for dense + ColBERT vectors
2. Implement `gnosis/services/hybrid_search.py` using Qdrant three-vector collection schema
3. Implement `gnosis/routers/search.py`
4. Write tests for hybrid search ranking correctness

**Phase 4 — Graph**
1. Implement `gnosis/routers/graph.py` — reads link table from PostgreSQL, formats as `{nodes: [], edges: []}` for frontend
2. Implement `GET /graph/clusters` using NetworkX Louvain community detection
3. Implement `GET /graph/path/{from_id}/{to_id}` using NetworkX shortest path

**Phase 5 — AI**
1. Implement `gnosis/services/llm_provider.py` with three-tier provider: Ollama → Groq → OpenAI with auto-fallback
2. Implement `gnosis/services/graph_rag.py` with LightRAG initialized on startup, notes ingested on create/update
3. Implement `gnosis/routers/ai.py` with all AI endpoints
4. Implement SSE streaming for `/api/v1/ai/stream/chat`

**Phase 6 — Document Ingestion**
1. Implement `gnosis/services/document_parser.py` supporting PDF/DOCX/PPTX/XLSX/image
2. Implement `gnosis/routers/ingest.py`
3. Write tests for each file format

**Phase 7 — MCP Server**
1. Mount `FastApiMCP` in `gnosis/main.py` as specified
2. Verify `claude mcp add gnosis http://localhost:8011/mcp` connects and tools are discoverable
3. Write MCP tool descriptions in FastAPI route docstrings (these become MCP tool descriptions)

**Phase 8 — Frontend**
1. Scaffold Vite + React + TypeScript project with tailwind, shadcn/ui
2. Generate TypeScript API client from FastAPI OpenAPI schema
3. Implement `NoteEditor.tsx` with TipTap + WikiLink extension
4. Implement `GraphView2D.tsx` with react-force-graph-2d
5. Implement `CommandPalette.tsx` with Cmd+K shortcut
6. Implement `AiChat.tsx` with SSE streaming display
7. Implement all pages specified in Part V
8. Write Playwright E2E tests for core workflows

**Phase 9 — Polish & CI**
1. Write `.github/workflows/ci.yml` with lint, test, build stages
2. Write `CLAUDE.md` at project root describing the codebase for future AI agent sessions
3. Write `DEVELOPMENT.md` with setup instructions
4. Ensure `docker compose up` brings up entire stack with a single command

### Constraints for the AI Agent

- **Do NOT use** `Any` types in TypeScript. Use `unknown` with type guards.
- **Do NOT hard-code** Qdrant collection names, table names, or paths — all in `config.py`
- **Do NOT create** a proprietary note format. All writes must produce valid `.md` files readable by any text editor
- **Do NOT require** Ollama to be running for the API to start — gracefully degrade with warning logs
- **Do NOT** skip tests. Every router function must have at least one test
- **Do NOT** add authentication requirements to the MCP server endpoints (they run on localhost only)
- **DO** write JSDoc comments on all TypeScript functions
- **DO** write Google-style docstrings on all Python functions
- **DO** export all environment variables in a `.env.example` file
- **DO** use `ruff` for Python linting (configured in `pyproject.toml`)

### Output Format Contract

The agent should produce:
- A complete `gnosis/` repository directory
- `README.md` with architecture diagram and quick-start instructions
- `CLAUDE.md` with project context for AI agent sessions
- `docker-compose.yml` and `.env.example`
- All migrations in `alembic/versions/`
- Test suite with ≥85% coverage on services and routers
- GitHub Actions CI workflow

---

## Part X: Future Enhancement Roadmap

These features are explicitly out of scope for the initial build but should be architected for in the data model:

| Feature | Description | Prerequisite |
|---|---|---|
| **Spaced Repetition** | Anki-style review scheduling for notes (SM-2 algorithm on `last_reviewed` field) | `last_reviewed` frontmatter field already specified |
| **EEG/Neurolink Integration** | Meditation session notes auto-generated from Neurolink session data; EEG state tags on journal entries | TriliumNext ETAPI pattern from [^57][^63] |
| **Multi-user** | Shared vaults with per-user PARA namespaces and collaborative links | Auth system already JWT-based |
| **Zotero Integration** | Auto-import citations → literature notes in `70-sources/` | ETAPI pattern |
| **Voice Capture** | Whisper transcription → inbox note creation | Ingest pipeline already structured for this |
| **Contemplative Mode** | Distraction-free full-screen editor with optional ambient sound, session timer | UI page spec supports adding this |
| **VSM Dashboard** | Cybernetic Viable Systems Model view of your knowledge domains | Graph clustering already planned |

---

## Appendix A: Environment Variables Reference

```bash
# .env.example
# Database
POSTGRES_PASSWORD=change_in_production
DATABASE_URL=postgresql+asyncpg://gnosis:${POSTGRES_PASSWORD}@gnosis-db:5432/gnosis

# Vector Store
QDRANT_URL=http://gnosis-vector:6333

# Vault
VAULT_PATH=./vault          # Absolute or relative path to your Markdown vault

# Auth
SECRET_KEY=generate-with-openssl-rand-hex-32
ACCESS_TOKEN_EXPIRE_MINUTES=10080  # 7 days

# AI Providers (optional — Ollama is default)
OLLAMA_BASE_URL=http://gnosis-ollama:11434
OLLAMA_LLM_MODEL=qwen2.5:14b
OLLAMA_EMBED_MODEL=nomic-embed-text

# External LLM (optional fallbacks)
OPENAI_API_KEY=
GROQ_API_KEY=
OPENROUTER_API_KEY=

# Application
LOG_LEVEL=info
DEBUG=false
```

---

## Appendix B: Recommended Ollama Models

```bash
# Pull these before starting Gnosis with local AI
ollama pull qwen2.5:14b          # Primary LLM for generation, critique, summaries
ollama pull nomic-embed-text      # Embeddings (768-dim, fast, high quality) 
ollama pull llava:13b             # Optional: image OCR + visual note generation
```

Minimum hardware: 16 GB RAM + 8 GB VRAM (GPU optional but recommended for qwen2.5:14b).
Minimum without GPU: run `qwen2.5:7b` instead; disable LightRAG entity extraction (use Groq API instead).


---

## References

1. [GitHub - tadata-org/fastapi_mcp: Expose your FastAPI endpoints as Model Context Protocol (MCP) tools, with Auth!](https://github.com/tadata-org/fastapi_mcp) - Expose your FastAPI endpoints as Model Context Protocol (MCP) tools, with Auth! - tadata-org/fastapi...

2. [FastAPI-MCP: Simplifying the Integration of FastAPI with AI Agents](https://www.infoq.com/news/2025/04/fastapi-mcp/) - A new open-source library, FastAPI-MCP, is making it easier for developers to connect traditional Fa...

3. [hybrid-search-implementation.md - qdrant-rag-mcp](https://github.com/ancoleman/qdrant-rag-mcp/blob/main/docs/technical/hybrid-search-implementation.md) - Contribute to ancoleman/qdrant-rag-mcp development by creating an account on GitHub.

4. [GraphRAG and LightRAG in 2026: Knowledge Graphs for ...](https://callsphere.ai/blog/vw6g-microsoft-graphrag-knowledge-graph-2026)

5. [Demo: Implementing a Hybrid Search System - Qdrant](https://qdrant.tech/course/essentials/day-3/hybrid-search-demo/) - Step-by-step demo on implementing hybrid search using Qdrant's Universal Query API. Explore dense vs...

6. [Final Project: Production-Ready Documentation Search Engine](https://qdrant.tech/course/essentials/day-6/final-project/) - Create a complete documentation search system with Qdrant, featuring hybrid retrieval, multivector r...

7. [LightRAG - The Graph-Based RAG That Outperforms Everything](https://teodoracoach.substack.com/p/day-24-lightrag-the-graph-based-rag) - RAG for Healthcare | Day 24 of 35 | Free

27. [Vector DB vs Knowledge Graph in 2026: Pick for RAG](https://futureagi.com/blog/vector-databases-knowledge-graphs-rag-2025/) - Vector databases vs knowledge graphs for RAG in 2026. Pinecone, Weaviate, Qdrant, Milvus, Chroma vs ...

31. [Constructing Knowledge Graphs With Neo4j GraphRAG for ...](https://neo4j.com/blog/developer/knowledge-graphs-neo4j-graphrag-for-python/) - The new package includes a Knowledge Graph Builder to help you convert your unstructured and structu...

49. [XMPP for cloud computing in bioinformatics supporting discovery and invocation of asynchronous web services](https://pmc.ncbi.nlm.nih.gov/articles/PMC2755485/) - ...and the inability for services to send status notifications. Several complementary workarounds ha...

57. [Deploy AnythingLLM | HOSTIM.DEV](https://hostim.dev/docs/templates/anythingllm/) - Deploy AnythingLLM with Docker and persistent storage in one click. A self-hosted, chat-based interf...

63. [AnythingLLM/docker/HOW_TO_USE_DOCKER.md at master · leeevertime/AnythingLLM](https://github.com/leeevertime/AnythingLLM/blob/master/docker/HOW_TO_USE_DOCKER.md) - Contribute to leeevertime/AnythingLLM development by creating an account on GitHub.

74. [OpenHands | The Open Platform for Cloud Coding Agents](https://www.openhands.dev) - Meet OpenHands, the open-source, model-agnostic platform for cloud coding agents. Automate real engi...

82. [Frameworks for working with graph visualizations, which one do you ...](https://www.reddit.com/r/reactjs/comments/1f9lis9/frameworks_for_working_with_graph_visualizations/) - We're evaluating Graph visualization frameworks that can effectively scale to handle large graphs wi...

99. [alamkanak/fastapi-mcp-openapi - GitHub](https://github.com/alamkanak/fastapi-mcp-openapi) - A FastAPI library that provides Model Context Protocol (MCP) tools for endpoint introspection and Op...

