# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

> Inherits from project root CLAUDE.md. This file adds backend-specific context.

## Commands

```bash
# Activate venv (required before all commands)
cd assets/backend && source .venv/bin/activate

# Run server
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Tests (tests live in assets/tests/, NOT assets/backend/tests/)
pytest ../tests/ -v
pytest ../tests/test_api.py -v
pytest ../tests/test_api.py::test_health -v

# Package management (use uv, not pip)
uv add <package>
uv sync

# Health check
curl http://localhost:8000/health
```

## Current State

- `main.py`: ~2279 lines, 45+ route endpoints — all flat, no router split yet
- 5 global variables: `agent`, `postgres_storage`, `vector_store`, `active_connections`, `connection_tasks`
- No `routers/`, `services/`, `infrastructure/`, or `dependencies/` directories exist yet
- `enhanced_rag.py` has direct `pymilvus` imports (needs encapsulation)

## Architecture — Module Dependency Graph

```
main.py ──→ agent.py ──→ client.py (MCPClient)
  │            │            └──→ tools/mcp_servers/*.py
  │            ├──→ prompts.py
  │            ├──→ postgres_storage.py ──→ asyncpg
  │            └──→ langfuse_client.py
  │
  ├──→ config.py (ConfigManager)
  ├──→ models.py (Pydantic request models)
  ├──→ vector_store.py ──→ langchain_milvus, langchain_openai
  ├──→ postgres_storage.py
  ├──→ utils.py
  ├──→ errors.py
  ├──→ auth.py (optional JWT via SUPABASE_JWT_SECRET)
  └──→ openai_compatible/router.py ──→ openai_compatible/models.py
```

`enhanced_rag.py` is standalone — called from `tools/mcp_servers/rag.py`, not from `main.py` directly.

## Key Files

| File | Lines | Role |
|------|-------|------|
| `main.py` | ~2279 | All 45+ endpoints (needs splitting) |
| `agent.py` | ~791 | LangGraph ChatAgent with MCP tool integration |
| `enhanced_rag.py` | ~1381 | Hybrid search: Milvus vector + BM25 + reranking |
| `vector_store.py` | ~807 | LangChain-based Milvus wrapper |
| `postgres_storage.py` | ~571 | Chat history + image storage via asyncpg |
| `config.py` | ~165 | Thread-safe config with file-change detection |
| `errors.py` | ~254 | Unified error response system |
| `auth.py` | ~119 | Optional JWT middleware |
| `client.py` | ~92 | MCP client for tool discovery |

## Route Map (all in main.py)

```
Health:     GET /health, /health/rag, /metrics, /debug/config
            POST /debug/rebuild-bm25
WebSocket:  WS /ws/chat/{chat_id}
Upload:     POST /upload-image, /ingest
            GET /ingest/status/{task_id}
Sources:    GET/POST /sources, /sources/vector-counts, /sources/reindex
            DELETE /sources/{source_name}
Knowledge:  GET/POST /knowledge/status, /knowledge/sync
            DELETE /knowledge/sources/{source_name}
Config:     GET/POST /selected_sources, /selected_model
            GET /available_models
Chats:      GET /chats, /chat_id, /chat/{chat_id}/metadata
            POST /chat_id, /chat/rename, /chat/new
            DELETE /chat/{chat_id}, /chats/clear
Collections: DELETE /collections/{name}, /collections
RAG:        GET /test/rag, /test/vector-stats
            GET/POST /rag/llamaindex/config, /rag/llamaindex/query, /rag/llamaindex/stats
            POST /rag/llamaindex/cache/clear
            GET /rag/llamaindex/cache/stats
Admin:      GET /admin/rag/stats, /admin/rag/sources, /admin/conversations
            POST /admin/rag/sources/select, /admin/rag/sources/select-all, /admin/rag/sources/deselect-all
            GET /admin/conversations/{chat_id}/messages
OpenAI:     (mounted) /v1/chat/completions, /v1/models, /v1/embeddings
```

## enhanced_rag.py — Hybrid Search Pipeline

This is the most complex module. It implements a multi-stage retrieval pipeline:

1. Query expansion via HyDE (Hypothetical Document Embeddings) using the LLM
2. Parallel search: Milvus vector search + BM25 keyword search
3. Reciprocal Rank Fusion to merge results
4. LLM-based reranking (Reranker class)
5. QueryCache (in-memory or Redis) for deduplication

Key classes: `Qwen3Embedding`, `BM25Indexer`, `Reranker`, `HyDEQueryExpander`, `QueryCache`, `RedisQueryCache`

Entry point: `async enhanced_rag_query(query, sources, ...)` — returns ranked documents + answer.

## Non-Obvious Patterns

### ChatAgent Lifecycle
- Created via `await ChatAgent.create(...)` (async factory) — never `ChatAgent(...)`
- Uses LangGraph `StateGraph` with `MemorySaver` — conversation state is in-memory per session
- `SENTINEL = object()` marks end of streaming — check for it in WebSocket handlers
- MCP tools auto-discovered at startup via `client.py`

### Global State (to be refactored)
- `agent` is initialized in `lifespan()` context manager, set via `global agent`
- `postgres_storage` and `vector_store` are module-level singletons
- `active_connections: Dict[str, Set[WebSocket]]` — multiple WS connections per chat_id
- `connection_tasks: Dict[str, asyncio.Task]` — one processing task per chat_id

### ConfigManager
- `config.json` auto-created at startup from `MODELS` env var
- Thread-safe via `threading.Lock()` — use `config_manager.read_config()` not direct file access
- Detects file changes via mtime — no restart needed for config updates

### Error Handling
- Use `errors.py`: `raise APIError(ErrorCode.NOT_FOUND, "msg", status_code=404)`
- Or helpers: `return not_found_error("Chat", chat_id)`
- Never use raw `HTTPException`

### Logging
- JSON-structured: `logger.info({"message": "...", "key": val})`
- Import: `from logger import logger, log_request, log_response, log_error`
- Writes to `app.log` in backend working directory

### Rate Limiting
- Optional via `slowapi` — gracefully degrades if not installed (`RATE_LIMIT_AVAILABLE` flag)

## Refactoring Phases

### Phase 1: Split Routers (Priority Order)
- [ ] `routers/health.py` — /health, /health/rag, /metrics
- [ ] `routers/chats.py` — All chat CRUD
- [ ] `routers/knowledge.py` — /knowledge/*
- [ ] `routers/sources.py` — /sources/*
- [ ] `routers/rag.py` — /rag/*, /test/*
- [ ] `routers/admin.py` — /admin/*
- [ ] `routers/config.py` — /selected_*, /available_models
- [ ] `routers/upload.py` — /upload-image, /ingest
- [ ] `routers/websocket.py` — /ws/chat/*

### Phase 2: Extract Service Layer
- [ ] `services/chat_service.py`
- [ ] `services/knowledge_service.py`
- [ ] `services/rag_service.py`
- [ ] `services/health_service.py`

### Phase 3: Dependency Injection
- [ ] `dependencies/providers.py`

### Phase 4: Cleanup
- [ ] Remove all direct pymilvus imports from routers
- [ ] Verify main.py < 500 lines

## Verification Checklist (after each task)
- [ ] `curl http://localhost:8000/health` passes
- [ ] `pytest ../tests/ -v` passes
- [ ] No new global variables introduced
- [ ] main.py line count reduced
