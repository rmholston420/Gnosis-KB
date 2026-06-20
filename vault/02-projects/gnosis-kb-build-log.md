---
id: 20260601-gnosis-build-log
title: Gnosis KB Build Log
type: project
status: active
tags: gnosis, project, knowledge-management, software, build-log
created: 2026-06-01T08:00:00
modified: 2026-06-19T22:00:00
---

# Gnosis KB Build Log

Running log of architectural decisions, slice completions, and open questions for the Gnosis personal knowledge base application.

## Architecture Decisions

### ADR-001 — LightRAG for Graph-Level Retrieval
Qdrant handles semantic similarity search (vector-level). LightRAG adds a knowledge-graph layer that enables *thematic* queries: "what are the recurring themes in my notes on consciousness?" This is query-mode switching: `local` (entity lookup), `global` (thematic synthesis), `hybrid` (both).

**Status:** LightRAG installed; warm-up added to lifespan startup.

### ADR-002 — Per-User Vault Isolation
Each user gets their own LightRAG working directory at `LIGHTRAG_DATA_DIR/<user_id>/`. Qdrant payloads are stamped with `owner_id` for filter-level isolation. `scoped_note_stmt()` enforces read boundaries in every DB query.

**Status:** Implemented. Legacy `owner_id=NULL` notes visible via `include_null_owner=True` sentinel; backfill script (`scripts/backfill_owner_ids.py`) fixes these.

### ADR-003 — SSE Streaming via fetch() not EventSource
The auth header cannot be sent by the native `EventSource` API. Using `fetch()` + `ReadableStream` in the frontend gives full control over headers while retaining streaming.

**Status:** Implemented in `AIChat.tsx`.

## Slice Completion Log

| Slice | Description | Status |
|---|---|---|
| 1 | FastAPI skeleton, auth, notes CRUD | ✅ Done |
| 2 | Qdrant vector store, semantic search | ✅ Done |
| 3 | LightRAG graph-RAG, SSE endpoint | ✅ Done |
| 4 | Frontend SSE wiring, owner backfill, vault seed, LightRAG warm-up | ✅ Done |

## Open Questions
- [ ] Should we add a `/api/v1/ingest/lightrag` endpoint that triggers `graph_rag.ingest_note()` for a given note, callable from the UI?
- [ ] The `graph_rag.initialize()` warm-up assumes `user_id=1` is always the primary user. Should we warm up *all* users present in the DB at startup?
- [ ] Add Alembic migration for the `owner_id` backfill rather than a standalone script?
