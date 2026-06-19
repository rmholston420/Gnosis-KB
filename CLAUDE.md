# Gnosis KB — CLAUDE.md

Project context for AI coding agents. Read this file at the start of every session.

## What is Gnosis?

Gnosis is a sovereign, Linux-native, AI-augmented personal knowledge base built on
FastAPI + React + PostgreSQL + Qdrant + LightRAG. All notes are plain Markdown files
in `~/gnosis-vault/`. The PostgreSQL DB and Qdrant vector store are **derived caches**
— deleting them loses no knowledge.

## Repo Layout

```
backend/gnosis/
  config.py          — pydantic-settings; all env vars live here
  database.py        — async SQLAlchemy engine + get_db dependency
  main.py            — FastAPI app factory, middleware, router registration, MCP mount
  core/
    auth.py          — JWT + bcrypt; AUTH_REQUIRED=false auto-logins as admin
    rate_limit.py    — slowapi Limiter singleton
    logging.py       — JSON or text structured logging
  models/            — SQLAlchemy ORM (note.py, user.py, tag.py, review_card.py)
  schemas/           — Pydantic request/response (note.py, auth.py, graph.py, search.py)
  routers/           — FastAPI route handlers
    notes.py         — CRUD + backlinks
    search.py        — hybrid (Qdrant+FTS), fulltext, suggest
    review.py        — SM-2 spaced repetition
    tags.py / folders.py
    graph.py         — /graph/, /neighborhood, /path, /clusters, /stats
    auth.py          — /auth/token, /register, /me
    export.py        — /export/vault.zip, /export/note/{id}.md, /export/note/{id}.pdf
    health.py        — /health/ (readiness), /health/ping (liveness)
  services/
    fts.py           — PostgreSQL tsvector fulltext_search + suggest_completions
    hybrid_search.py — Qdrant BM25+dense RRF fusion
    vault_sync.py    — watchdog filesystem → DB sync
    embeddings.py    — fastembed dense + ColBERT
    vector_store.py  — Qdrant collection management
    graph_rag.py     — LightRAG integration
  alembic/versions/
    001_initial_schema.py
    0002_add_review_cards.py
    0003_add_fts_tsvector.py
    0004_add_users.py

frontend/src/
  App.tsx            — router + sidebar nav
  main.tsx           — ReactDOM mount + service worker registration
  registerSW.ts      — PWA service worker registration
  sw.ts              — Service worker (cache-first static, network-first API)
  pages/
    NotesPage.tsx    — vault browser
    NoteEditor.tsx   — TipTap editor + wikilink preview + backlinks
    SearchPage.tsx   — hybrid/fulltext/suggest search UI
    ReviewPage.tsx   — SM-2 spaced repetition UI
    GraphPage.tsx    — react-force-graph-2d knowledge graph
    SettingsPage.tsx — health dashboard + vault export
  components/
    WikilinkPreview.tsx / WikilinkPopup.tsx / BacklinkPanel.tsx
  api/client.ts      — axios instance

nginx/gnosis.conf    — HTTP reverse proxy with CSP headers
public/manifest.json — PWA manifest
```

## Key Conventions

- **Two-call DB pattern**: `AsyncSessionLocal = get_session_factory(engine)` then
  `async with AsyncSessionLocal() as db:` — never call `get_session_factory()` twice.
- **AUTH_REQUIRED=false** (default): every request auto-resolves to the bootstrap admin;
  no login screen needed for single-user local deployment.
- **Rate limits**: 200 req/min globally via slowapi; apply `@limiter.limit("N/minute")`
  per-route for stricter endpoints.
- **Migrations**: always add new Alembic migrations in `alembic/versions/` with sequential
  IDs (0005, 0006, …). Never edit existing migration files.
- **JSON logging**: set `LOG_FORMAT=json` in production for log aggregators.
- **PDF export**: disabled by default; set `ENABLE_PDF_EXPORT=true` and install weasyprint.

## Session 3 Slices Completed (F–K)

- **F. Auth** — JWT + bcrypt single/multi-user; `core/auth.py`, `routers/auth.py`,
  `models/user.py`, migration `0004_add_users.py`, bootstrap admin on first run.
- **G. Graph view** — `routers/graph.py` (5 endpoints), `schemas/graph.py`,
  `GraphPage.tsx` with react-force-graph-2d, colour legend, stats overlay, zoom controls.
- **H. Export** — `routers/export.py` (vault.zip, single-note .md, optional PDF via
  WeasyPrint); `SettingsPage.tsx` with one-click download.
- **I. PWA** — `public/manifest.json`, `src/sw.ts` (cache-first static / network-first API),
  `src/registerSW.ts`, meta tags in `index.html`.
- **J. Rate limiting** — `core/rate_limit.py` (slowapi Limiter), wired in `main.py`;
  `nginx/gnosis.conf` updated with CSP + security headers.
- **K. Observability** — `core/logging.py` (JSON/text structured logging),
  `routers/health.py` (`/health/` readiness + `/health/ping` liveness with DB+Qdrant checks).

## Environment Variables (key ones)

```bash
AUTH_REQUIRED=false          # true = enforce JWT login
SECRET_KEY=<openssl rand>    # change before exposing publicly
INITIAL_ADMIN_EMAIL=admin@gnosis.local
INITIAL_ADMIN_PASSWORD=gnosis_admin
LOG_FORMAT=json              # production structured logging
ENABLE_PDF_EXPORT=false      # true + pip install weasyprint
```

## Next Session Hooks

- **AI Router** — `routers/ai.py` (LightRAG chat, summarise, suggest-links, critique,
  orphan audit, SSE streaming) — the largest remaining feature.
- **Ingest Router** — `routers/ingest.py` (PDF/DOCX/PPTX/XLSX/image → literature note).
- **TipTap WikiLink extension** — `components/editor/WikiLinkExtension.ts`.
- **Command palette** — `components/search/CommandPalette.tsx` (cmdk, Cmd+K).
- **Playwright E2E tests** — `tests/e2e/test_workflow.py`.
