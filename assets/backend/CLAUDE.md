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

Backend refactoring is **complete** (Phases 1-6). `main.py` reduced from 2279 to 230 lines. `enhanced_rag.py` (1381 lines) deleted — replaced by `rag/` package. `agent.py` (785 lines) decomposed into `agent/` package. All legacy routers consolidated into `api_v1.py`. `vector_store.py` migrated to `services/vector_store_service.py`.

- `main.py`: 230 lines — app factory, lifespan, middleware, exception handlers, router registration
- `routers/`: 4 files, 962 lines — thin HTTP handlers with `Depends()` injection, delegates to services
- `services/`: 7 files, 1502 lines — stateless business logic (chat, health, ingest, knowledge, rag, vector_store)
- `rag/`: 6 files, 978 lines — decomposed RAG pipeline
- `infrastructure/`: 5 files, 547 lines — milvus_client, embedding_client, llm_client, cache
- `dependencies/`: 2 files, 72 lines — FastAPI `Depends()` factories
- `agent/`: 6 files, 786 lines — LangGraph ChatAgent with MCP tool integration (decomposed from monolithic `agent.py`)
- Global variables eliminated from `main.py` — uses `app.state` + `@lru_cache` singletons

## Architecture — Module Dependency Graph

```
main.py ──→ routers/ (api_v1, chat_stream, health)
  │              │
  │              ├──→ dependencies/providers.py ──→ singletons
  │              │
  │              ├──→ services/ (chat, health, ingest, knowledge, rag, vector_store)
  │              │       └──→ infrastructure/ (milvus_client, embedding_client, llm_client, cache)
  │              │
  │              └──→ rag/ (pipeline, bm25, reranker, hyde, fusion)
  │                      └──→ infrastructure/
  │
  ├──→ agent/ (core, graph, streaming, formatting, observability)
  │       │──→ client.py (MCPClient)
  │       │       └──→ tools/mcp_servers/*.py
  │       ├──→ prompts.py
  │       ├──→ postgres_storage.py ──→ asyncpg
  │       └──→ observability.py ──→ langfuse (v2)
  │
  ├──→ config.py (ConfigManager)
  ├──→ models.py (Pydantic request models)
  ├──→ errors.py
  ├──→ auth.py (optional JWT)
  └──→ openai_compatible/router.py
```

**Call chain**: `Router → Service → Infrastructure → External API`

## Key Files

| File | Lines | Role |
|------|-------|------|
| `main.py` | 230 | App factory + lifespan + router mount |
| **Agent package** | | |
| `agent/__init__.py` | 14 | Re-exports ChatAgent |
| `agent/core.py` | 280 | ChatAgent class: create(), query() |
| `agent/graph.py` | 250 | LangGraph StateGraph: build_graph(), tool_node(), generate() |
| `agent/streaming.py` | 127 | SSE streaming: _stream_response(), _queue_writer() |
| `agent/formatting.py` | 59 | Message format conversion (LangGraph ↔ OpenAI) |
| `agent/observability.py` | 56 | Langfuse v2 tracing integration |
| **Routers** | | |
| `routers/api_v1.py` | 719 | All `/api/v1/` endpoints (chats, sources, RAG, upload, knowledge, admin) |
| `routers/chat_stream.py` | 164 | SSE streaming: `/api/v1/chats/{id}/completions` |
| `routers/health.py` | 62 | Health checks, metrics, debug |
| **Services** | | |
| `services/vector_store_service.py` | 584 | VectorStore class (Milvus + langchain_milvus) |
| `services/knowledge_service.py` | 423 | 3-layer reconciliation (config+files+vectors) |
| `services/ingest_service.py` | 182 | Document loading, chunking, indexing |
| `services/health_service.py` | 156 | Aggregate health checks, metrics |
| `services/chat_service.py` | 83 | Chat CRUD, dedup'd from 3 routers |
| `services/rag_service.py` | 54 | Thin wrapper for RAG pipeline calls |
| **RAG pipeline** | | |
| `rag/pipeline.py` | 412 | RAG orchestrator: cache → HyDE → search → fuse → rerank → answer |
| `rag/bm25.py` | 208 | BM25Indexer using infrastructure.milvus_client |
| `rag/reranker.py` | 163 | Async LLM-based cross-encoder reranker |
| `rag/hyde.py` | 91 | Async HyDE query expansion |
| `rag/fusion.py` | 74 | Reciprocal Rank Fusion (pure function) |
| **Infrastructure** | | |
| `infrastructure/cache.py` | 253 | QueryCache (memory) + RedisQueryCache |
| `infrastructure/milvus_client.py` | 150 | Centralized pymilvus access (10 functions) |
| `infrastructure/embedding_client.py` | 65 | AsyncQwen3Embedding (async httpx) |
| `infrastructure/llm_client.py` | 33 | AsyncOpenAI singleton |
| `dependencies/providers.py` | 54 | FastAPI Depends() factories |

## Route Map

All routes under `/api/v1/` prefix except health (root) and OpenAI-compat (`/v1/`).

```
routers/health.py (no prefix):
  GET  /health                          Health check
  GET  /health/rag                      RAG health check
  GET  /metrics                         System metrics
  GET  /debug/config                    Debug config info
  POST /debug/rebuild-bm25             Rebuild BM25 index

routers/chat_stream.py (prefix: /api/v1):
  POST /api/v1/chats/{chat_id}/completions   SSE streaming chat
  POST /api/v1/chats/{chat_id}/stop          Stop generation

routers/api_v1.py (prefix: /api/v1):
  # RAG
  POST /api/v1/rag/query               RAG search query
  GET  /api/v1/rag/stats               RAG statistics
  GET  /api/v1/rag/config              RAG configuration
  POST /api/v1/rag/cache/clear         Clear RAG cache
  GET  /api/v1/rag/cache/stats         Cache statistics

  # Models
  GET  /api/v1/models/selected          Current model
  POST /api/v1/models/selected          Set model
  GET  /api/v1/models/available         Available models

  # Chats
  GET  /api/v1/chats                    List chats
  POST /api/v1/chats                    Create chat
  GET  /api/v1/chats/current            Get current chat
  PATCH /api/v1/chats/current           Update current chat
  GET  /api/v1/chats/{id}/messages      Chat messages
  GET  /api/v1/chats/{id}/metadata      Chat metadata
  PATCH /api/v1/chats/{id}/metadata     Update metadata
  DELETE /api/v1/chats/{id}             Delete chat
  DELETE /api/v1/chats                  Clear all chats

  # Sources
  GET  /api/v1/sources                  List sources
  GET  /api/v1/sources/vector-counts    Vector counts per source
  POST /api/v1/sources/reindex          Reindex source
  DELETE /api/v1/sources/{name}         Delete source
  GET  /api/v1/selected-sources         Selected sources
  POST /api/v1/selected-sources         Set selected sources

  # Upload & Ingest
  POST /api/v1/upload/image             Upload image
  POST /api/v1/ingest                   Ingest documents
  GET  /api/v1/ingest/status/{task_id}  Ingestion status

  # Knowledge
  GET  /api/v1/knowledge/status         Knowledge sync status
  POST /api/v1/knowledge/sync           Trigger sync
  DELETE /api/v1/knowledge/sources/{name}  Delete knowledge source

  # Admin
  DELETE /api/v1/admin/collections/{name}  Delete collection
  DELETE /api/v1/admin/collections         Delete all collections
  GET  /api/v1/admin/test/rag              Test RAG query
  GET  /api/v1/admin/test/vector-stats     Vector statistics
  GET  /api/v1/admin/rag/stats             RAG stats (admin)
  GET  /api/v1/admin/rag/sources           List RAG sources
  POST /api/v1/admin/rag/sources/select    Select source
  POST /api/v1/admin/rag/sources/select-all   Select all
  POST /api/v1/admin/rag/sources/deselect-all Deselect all
  GET  /api/v1/admin/conversations         List conversations
  GET  /api/v1/admin/conversations/{id}/messages  Conversation messages

openai_compatible/router.py (prefix: /v1):
  GET  /v1/models                       List models
  GET  /v1/models/{model_id}            Get model
  POST /v1/chat/completions             Chat completion
  POST /v1/embeddings                   Generate embeddings
```

## RAG Pipeline (`rag/` package)

Multi-stage retrieval pipeline, fully async:

1. Cache check (Redis + memory) — `infrastructure/cache.py`
2. HyDE query expansion (optional) — `rag/hyde.py`
3. Parallel search via `asyncio.gather()` — `rag/pipeline.py`
   - Vector search: Milvus + Qwen3 embeddings — `rag/pipeline.py:vector_search()`
   - BM25 keyword search — `rag/bm25.py`
4. Reciprocal Rank Fusion — `rag/fusion.py`
5. Cross-encoder reranking — `rag/reranker.py`
6. LLM answer generation — `rag/pipeline.py:generate_answer()`
7. Cache store

Entry point: `from rag import enhanced_rag_query`

## Non-Obvious Patterns

### ChatAgent Lifecycle
- Created via `await ChatAgent.create(...)` (async factory) — never `ChatAgent(...)`
- Uses LangGraph `StateGraph` with `MemorySaver` — conversation state is in-memory per session
- `SENTINEL = object()` marks end of streaming — check for it in SSE handlers
- MCP tools auto-discovered at startup via `client.py`
- Agent decomposed into mixins: `ChatAgent(_GraphMixin, _StreamingMixin)`

### Dependency Injection
- `dependencies/providers.py`: `@lru_cache()` singletons for ConfigManager, PostgresStorage
- `agent` + `vector_store` stored on `app.state` (async-initialized in lifespan)
- Routers use `Depends(get_config_manager)`, `Depends(get_postgres_storage)`, etc.

### Infrastructure Layer
- **All** `pymilvus` access goes through `infrastructure/milvus_client.py` (R2 compliant)
- Embedding: `AsyncQwen3Embedding` uses async `httpx` (was sync `requests`)
- LLM: `get_llm_client()` returns shared `AsyncOpenAI` singleton (was per-call creation)
- Cache key includes `query + sources + top_k + use_hybrid` for correctness

### VectorStore (services/vector_store_service.py)
- Uses `langchain_milvus.Milvus` which requires sync `embed_documents()`/`embed_query()` interface
- `CustomEmbeddings` class provides sync embedding via `requests.post()` + `ThreadPoolExecutor`
- NOT interchangeable with `AsyncQwen3Embedding` (different interface: sync vs async)
- `vector_store.py` at project root is a backward-compatible re-export shim (17 lines)

### Service Layer
- Stateless module-level async functions — no classes (except VectorStore)
- Accept dependencies as parameters (no global state)
- Return raw data — routers handle HTTP response formatting
- Business logic dedup'd from 3+ routers into single service functions

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

## Docker Bind Mount & .venv — Isolation

The backend uses `./backend:/app` bind mount. An anonymous volume `- /app/.venv` in `docker-compose.yml` **isolates** the container's `.venv` from the host's, preventing the root-ownership conflict.

### How It Works
- Host `.venv`: created by `uv sync` on host, owned by `htzl`, uses host Python (`/usr/bin/python3`)
- Container `.venv`: lives in the anonymous volume, owned by root, uses container Python (`/usr/local/bin/python3`)
- They never interfere with each other

### Rules
- **NEVER remove** the `- /app/.venv` line from `docker-compose.yml` volumes
- Run `uv sync` on host to manage host `.venv` (for pytest, IDE, etc.)
- Container manages its own `.venv` independently via Dockerfile
- **NEVER `docker compose restart backend`** after code edits — uvicorn `--reload` handles it automatically

### Recovery (if .venv gets corrupted)
```bash
docker run --rm -v $(pwd)/backend:/app python:3.12 rm -rf /app/.venv
cd assets/backend && uv sync
cd assets && docker compose up -d backend
```

## Verification Checklist (after each task)
- [ ] `curl http://localhost:8000/health` passes
- [ ] `pytest ../tests/ -v` passes
- [ ] No new global variables introduced
- [ ] No direct `pymilvus` imports outside `infrastructure/milvus_client.py`
