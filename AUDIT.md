# Gnosis-KB Backend Audit Log

## Audit: 2026-06-26 (HEAD 70fcfae)

Full re-audit of `backend/gnosis` — all 20 items from the original
audit report confirmed resolved. No new issues found.

### Resolved Items

| # | Severity | File | Issue | Status |
|---|---|---|---|---|
| 1 | 🔴 Critical | `database.py` | `_AsyncSessionLocalProxy.__aenter__` correct | ✅ |
| 2 | 🔴 Critical | `core/events.py` | `init_db()` called on startup | ✅ |
| 3 | 🔴 Critical | `services/vault_sync.py` | `upsert_note` call correct (sync fn) | ✅ |
| 4 | 🔴 Critical | `services/embeddings.py` | ERROR-level logging on failures | ✅ |
| 5 | 🟠 High | `config.py` | No duplicate `qdrant_collection` fields | ✅ |
| 6 | 🟠 High | `services/vault_sync.py` | `asyncio.get_running_loop()` replaces deprecated `get_event_loop()` | ✅ |
| 7 | 🟠 High | `.gitignore` | `*.db` excluded | ✅ |
| 8 | 🟡 Medium | `routers/search.py` | Qdrant errors fall back to FTS with logging | ✅ |
| 9 | 🟡 Medium | `routers/notes.py` | Unexpected exceptions propagate to FastAPI global handler | ✅ |
| 10 | 🟡 Medium | `config.py` | Startup guard for default secret key | ✅ |
| 11 | 🟡 Medium | `routers/admin.py` | Auth guard (`require_user` + id==1 check) in place | ✅ |
| 12 | 🟡 Medium | `services/graph_rag.py` | LightRAG init errors surface at WARNING; no silent partial state | ✅ |
| 13 | 🔵 Low | `models/__init__.py` | Explicit `__all__` added | ✅ |
| 14 | 🔵 Low | `core/sm2_test.py` | Deleted from source package; canonical copy at `tests/test_sm2.py` | ✅ |
| 15 | 🔵 Low | `routers/ws.py` | `WebSocketDisconnect` + `CancelledError` handled; registry cleaned up | ✅ |
| 16 | 🔵 Low | `database.py` | Module-level globals initialised once; acceptable single-process use | ✅ |
| 17 | 🔵 Low | `services/fts.py` | FTS rebuild errors logged at ERROR; no silent degradation | ✅ |
| 18 | 🔵 Low | `services/ingest_queue.py` | Event loop lifecycle correct for single-process deploy | ✅ |
| 19 | 🔵 Low | `config.py` | `access_token_expire_minutes` documented; refresh-token noted as future work | ✅ |
| 20 | 🔵 Low | `routers/admin.py` | Rate limiting via global `slowapi` limiter; per-endpoint decorators noted as future hardening | ✅ |
