# Backend Refactoring Plan — ARCHIVED

> **Status: COMPLETE** — Phases 1-5 finished 2026-03-01. Phase 6 tracked in `delightful-tumbling-dolphin.md`.
> Generated: 2026-02-27
> Sources: CODE_REVIEW.md (5.5/10), RAG_ANALYSIS.md, CLAUDE.md R1-R5
> Constraint: **废弃所有 Legacy 路由，只保留 /api/v1/***

---

## 1. Current State

| File | Lines | Problem |
|------|-------|---------|
| main.py | 2279 | God file: 45+ routes, 5 globals, all logic inline |
| agent.py | 791 | God class: model init + MCP + streaming + observability |
| enhanced_rag.py | 1381 | 7 classes in one file, sync blocking, sequential search |
| vector_store.py | 807 | Direct pymilvus, sync ThreadPoolExecutor |
| postgres_storage.py | 571 | Well-designed (keep as-is, minor DI changes) |
| **Total** | **7050** | |

5 global variables: `agent`, `postgres_storage`, `vector_store`, `active_connections`, `connection_tasks`
27 legacy flat routes coexist with /api/v1/ — all legacy routes will be **deleted**.

---

## 2. Target Architecture

```
assets/backend/
├── main.py                    # <150 lines: app factory + lifespan + router mount
├── routers/
│   ├── __init__.py
│   ├── health.py              # /api/v1/health, /health/rag, /metrics
│   ├── chats.py               # /api/v1/chats/* (CRUD + messages + metadata)
│   ├── sources.py             # /api/v1/sources/*, /selected-sources
│   ├── knowledge.py           # /api/v1/knowledge/*
│   ├── rag.py                 # /api/v1/rag/* (query, stats, config, cache)
│   ├── admin.py               # /api/v1/admin/*
│   ├── config.py              # /api/v1/models (selected/available)
│   ├── upload.py              # /api/v1/upload-image, /ingest
│   └── websocket.py           # WS /api/v1/ws/chat/{chat_id}
├── services/
│   ├── __init__.py
│   ├── chat_service.py        # Chat CRUD + WS message handling
│   ├── rag_service.py         # RAG pipeline orchestration
│   ├── knowledge_service.py   # Knowledge sync, source management
│   ├── ingest_service.py      # File upload + background indexing
│   └── health_service.py      # Health check aggregation
├── infrastructure/
│   ├── __init__.py
│   ├── milvus_client.py       # ALL pymilvus consolidated here
│   ├── embedding_client.py    # Qwen3Embedding (async httpx)
│   ├── llm_client.py          # OpenAI client singleton
│   ├── cache.py               # QueryCache + RedisQueryCache
│   └── observability.py       # Langfuse + structured logging
├── rag/
│   ├── __init__.py
│   ├── pipeline.py            # enhanced_rag_query() orchestrator
│   ├── bm25.py                # BM25Indexer
│   ├── reranker.py            # LLM-based reranker
│   ├── hyde.py                # HyDE query expansion
│   └── fusion.py              # Reciprocal Rank Fusion
├── dependencies/
│   ├── __init__.py
│   └── providers.py           # FastAPI Depends() factories
├── agent.py                   # Slimmed ChatAgent (~300 lines)
├── config.py                  # ConfigManager (unchanged)
├── models.py                  # Pydantic models (expanded)
├── errors.py                  # Error system (unchanged)
├── auth.py                    # JWT middleware (unchanged)
├── logger.py                  # Logging (unchanged)
└── openai_compatible/         # OpenAI compat layer (unchanged)
```

---

## 3. Route Migration Table (Legacy → /api/v1/)

All legacy routes (left column) will be **DELETED**. Only /api/v1/* survives.

### Health & Debug
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `GET /health` | `GET /api/v1/health` | health.py |
| `GET /health/rag` | `GET /api/v1/health/rag` | health.py |
| `GET /metrics` | `GET /api/v1/metrics` | health.py |
| `GET /debug/config` | `GET /api/v1/debug/config` | health.py |
| `POST /debug/rebuild-bm25` | `POST /api/v1/debug/rebuild-bm25` | health.py |

### Chats
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `GET /chats` | `GET /api/v1/chats` | chats.py |
| `GET /chat_id` | `GET /api/v1/chats/current` | chats.py |
| `POST /chat_id` | `PATCH /api/v1/chats/current` | chats.py |
| `POST /chat/new` | `POST /api/v1/chats` | chats.py |
| `POST /chat/rename` | `PATCH /api/v1/chats/{chat_id}/metadata` | chats.py |
| `GET /chat/{chat_id}/metadata` | `GET /api/v1/chats/{chat_id}/metadata` | chats.py |
| `DELETE /chat/{chat_id}` | `DELETE /api/v1/chats/{chat_id}` | chats.py |
| `DELETE /chats/clear` | `DELETE /api/v1/chats` | chats.py |
| _(new)_ | `GET /api/v1/chats/{chat_id}/messages` | chats.py |

### Sources
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `GET /sources` | `GET /api/v1/sources` | sources.py |
| `GET /sources/vector-counts` | `GET /api/v1/sources/vector-counts` | sources.py |
| `POST /sources/reindex` | `POST /api/v1/sources:reindex` | sources.py |
| `DELETE /sources/{name}` | `DELETE /api/v1/sources/{name}` | sources.py |
| `GET /selected_sources` | `GET /api/v1/selected-sources` | sources.py |
| `POST /selected_sources` | `POST /api/v1/selected-sources` | sources.py |

### Knowledge
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `GET /knowledge/status` | `GET /api/v1/knowledge/status` | knowledge.py |
| `POST /knowledge/sync` | `POST /api/v1/knowledge/sync` | knowledge.py |
| `DELETE /knowledge/sources/{name}` | `DELETE /api/v1/knowledge/sources/{name}` | knowledge.py |

### RAG
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `GET /test/rag` | `GET /api/v1/rag/test` | rag.py |
| `GET /test/vector-stats` | `GET /api/v1/rag/vector-stats` | rag.py |
| `GET /rag/llamaindex/config` | `GET /api/v1/rag/config` | rag.py |
| `POST /rag/llamaindex/query` | `POST /api/v1/rag/query` | rag.py |
| `GET /rag/llamaindex/stats` | `GET /api/v1/rag/stats` | rag.py |
| `POST /rag/llamaindex/cache/clear` | `POST /api/v1/rag/cache:clear` | rag.py |
| `GET /rag/llamaindex/cache/stats` | `GET /api/v1/rag/cache/stats` | rag.py |

### Admin
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `GET /admin/rag/stats` | `GET /api/v1/admin/rag/stats` | admin.py |
| `GET /admin/rag/sources` | `GET /api/v1/admin/rag/sources` | admin.py |
| `POST /admin/rag/sources/select` | `POST /api/v1/admin/rag/sources:select` | admin.py |
| `POST /admin/rag/sources/select-all` | `POST /api/v1/admin/rag/sources:select-all` | admin.py |
| `POST /admin/rag/sources/deselect-all` | `POST /api/v1/admin/rag/sources:deselect-all` | admin.py |
| `GET /admin/conversations` | `GET /api/v1/admin/conversations` | admin.py |
| `GET /admin/conversations/{id}/messages` | `GET /api/v1/admin/conversations/{id}/messages` | admin.py |

### Config
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `GET /selected_model` | `GET /api/v1/models/selected` | config.py |
| `POST /selected_model` | `POST /api/v1/models/selected` | config.py |
| `GET /available_models` | `GET /api/v1/models` | config.py |

### Upload & Ingest
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `POST /upload-image` | `POST /api/v1/upload-image` | upload.py |
| `POST /ingest` | `POST /api/v1/ingest` | upload.py |
| `GET /ingest/status/{task_id}` | `GET /api/v1/ingest/status/{task_id}` | upload.py |

### WebSocket
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `WS /ws/chat/{chat_id}` | `WS /api/v1/ws/chat/{chat_id}` | websocket.py |

### Collections (merge into sources)
| Legacy Route | New /api/v1/ Route | Router |
|---|---|---|
| `DELETE /collections/{name}` | `DELETE /api/v1/sources/collections/{name}` | sources.py |
| `DELETE /collections` | `DELETE /api/v1/sources/collections` | sources.py |

### Kept As-Is (OpenAI Compatible)
| Route | Reason |
|---|---|
| `POST /v1/chat/completions` | OpenAI compat (openai_compatible/) |
| `GET /v1/models` | OpenAI compat |
| `POST /v1/embeddings` | OpenAI compat |

---

## 4. Implementation Phases

### Phase 1: Foundation — dependencies/ + infrastructure/ (Day 1) ✅ COMPLETE

**Goal**: Create DI layer and infrastructure wrappers so routers never touch raw clients.
**Result**: dependencies/ (2 files, 72 lines) + infrastructure/ (5 files, 517 lines) created. All pymilvus consolidated, async embedding client, LLM singleton, cache with proper keys.

#### Step 1.1: `dependencies/providers.py`
```python
from functools import lru_cache
from fastapi import Depends
from config import ConfigManager
from postgres_storage import PostgreSQLConversationStorage

@lru_cache()
def get_config_manager() -> ConfigManager:
    return ConfigManager("./config.json")

@lru_cache()
def get_postgres_storage() -> PostgreSQLConversationStorage:
    return PostgreSQLConversationStorage(
        host=os.getenv("POSTGRES_HOST", "postgres"),
        port=int(os.getenv("POSTGRES_PORT", 5432)),
        database=os.getenv("POSTGRES_DB", "chatbot"),
        user=os.getenv("POSTGRES_USER", "chatbot_user"),
        password=os.getenv("POSTGRES_PASSWORD", "chatbot_password"),
        cache_ttl=21600
    )

# Agent is async-initialized, so use app.state pattern
def get_agent(request: Request) -> ChatAgent:
    return request.app.state.agent

def get_vector_store(request: Request):
    return request.app.state.vector_store
```

#### Step 1.2: `infrastructure/milvus_client.py`
Consolidate ALL 7+ scattered `pymilvus` imports into one module:
- `main.py:155` → connections.connect in health check
- `main.py:858` → Collection() in vector-counts
- `main.py:1106` → connections/Collection in knowledge/status
- `enhanced_rag.py:145` → connections.connect in milvus_query()
- `enhanced_rag.py:328` → Collection in BM25Indexer.initialize()
- `vector_store.py:226` → direct pymilvus usage

Expose: `get_connection()`, `get_collection(name)`, `get_vector_counts(collection)`, `health_check()`

#### Step 1.3: `infrastructure/llm_client.py`
Singleton OpenAI client — currently `enhanced_rag.py:_generate_answer_with_llm()` creates a new client per call.
```python
@lru_cache()
def get_llm_client() -> AsyncOpenAI:
    return AsyncOpenAI(base_url=os.getenv("LLM_BASE_URL"), api_key=os.getenv("LLM_API_KEY"))
```

#### Step 1.4: `infrastructure/embedding_client.py`
Convert `Qwen3Embedding` from sync `requests` → async `httpx`:
```python
class AsyncQwen3Embedding:
    async def embed(self, texts: list[str]) -> list[list[float]]:
        async with httpx.AsyncClient() as client:
            resp = await client.post(self.url, json={"input": texts, "model": self.model})
            return [d["embedding"] for d in resp.json()["data"]]
```

#### Step 1.5: `infrastructure/cache.py`
Move `QueryCache` + `RedisQueryCache` from enhanced_rag.py. Fix cache key to include `sources + top_k`:
```python
def _cache_key(self, query: str, sources: list[str] | None, top_k: int) -> str:
    return hashlib.md5(f"{query}:{sorted(sources or [])}:{top_k}".encode()).hexdigest()
```

**Verification**: `pytest ../tests/ -v` passes, no import errors.

---

### Phase 2: Router Split — main.py → routers/ (Day 2-3) ✅ COMPLETE

**Goal**: main.py from 2279 → <150 lines. Delete ALL 27 legacy routes.
**Result**: main.py reduced to 230 lines. 11 router files created (2151 lines total). Includes chat_stream.py (SSE) and api_v1.py (versioned endpoints) beyond original plan. Legacy routes removed.

#### Execution Order (by dependency, simplest first):

1. **`routers/health.py`** (~80 lines) — Zero business logic, pure status checks
   - Move: health, health/rag, metrics, debug/config, debug/rebuild-bm25
   - Inject: `get_postgres_storage`, `get_agent`, `get_milvus_client` via Depends()
   - Replace direct `pymilvus` at main.py:155 with `infrastructure.milvus_client.health_check()`

2. **`routers/config.py`** (~50 lines) — Simple config reads/writes
   - Move: selected_model GET/POST, available_models
   - Inject: `get_config_manager` via Depends()

3. **`routers/chats.py`** (~120 lines) — CRUD operations
   - Move: all chat endpoints (list, create, current, metadata, rename, delete, clear)
   - Inject: `get_postgres_storage`, `get_config_manager`
   - Use existing v1 implementations as base (main.py:553-775)

4. **`routers/sources.py`** (~100 lines) — Source + collection management
   - Move: sources, vector-counts, reindex, selected-sources, collections
   - Replace direct `pymilvus` at main.py:858 with `infrastructure.milvus_client`
   - Inject: `get_config_manager`, `get_vector_store`, `get_milvus_client`

5. **`routers/upload.py`** (~80 lines) — File upload + ingest
   - Move: upload-image, ingest, ingest/status
   - Inject: `get_postgres_storage`, `get_vector_store`

6. **`routers/knowledge.py`** (~150 lines) — Most complex flat routes
   - Move: knowledge/status, knowledge/sync, knowledge/sources/{name}
   - Replace direct `pymilvus` at main.py:1106 with `infrastructure.milvus_client`
   - Inject: `get_config_manager`, `get_vector_store`, `get_milvus_client`

7. **`routers/rag.py`** (~100 lines) — RAG query + cache + stats
   - Move: rag/query, rag/stats, rag/config, rag/cache/clear, rag/cache/stats, rag/test, rag/vector-stats
   - Inject: `get_rag_service` (Phase 3)

8. **`routers/admin.py`** (~80 lines) — Admin dashboard endpoints
   - Move: admin/rag/stats, admin/rag/sources, admin/conversations
   - Inject: `get_postgres_storage`, `get_milvus_client`

9. **`routers/websocket.py`** (~200 lines) — WebSocket handler (most complex)
   - Move: ws/chat/{chat_id} + handle_chat_messages() helper (~170 lines)
   - Move `active_connections` + `connection_tasks` dicts into this module (local state, not global)
   - Inject: `get_agent`, `get_postgres_storage`

#### main.py After Phase 2:
```python
"""FastAPI app factory — router registration only."""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dependencies.providers import get_postgres_storage, get_config_manager
from agent import ChatAgent
from vector_store import create_vector_store_with_config
from errors import APIError, create_error_response
from logger import logger

@asynccontextmanager
async def lifespan(app: FastAPI):
    storage = get_postgres_storage()
    await storage.initialize()
    app.state.agent = await ChatAgent.create(...)
    app.state.vector_store = create_vector_store_with_config(get_config_manager())
    yield
    await storage.close()

app = FastAPI(title="Multi-Agent Chatbot", lifespan=lifespan)
app.add_middleware(CORSMiddleware, ...)

# Exception handlers
@app.exception_handler(APIError)
async def api_error_handler(request, exc): ...

# Mount routers
from routers import health, chats, sources, knowledge, rag, admin, config, upload, websocket
for router in [health, chats, sources, knowledge, rag, admin, config, upload, websocket]:
    app.include_router(router.router, prefix="/api/v1")

from openai_compatible import router as openai_router
app.include_router(openai_router)
```

**Verification**: `curl /api/v1/health` passes, all legacy routes return 404.

---

### Phase 3: RAG Pipeline Decomposition — enhanced_rag.py → rag/ (Day 4) ✅ COMPLETE

**Goal**: Split 1381-line monolith into focused modules. Fix critical perf bugs.
**Result**: rag/ package created (6 files, 978 lines). Hybrid search now parallel via asyncio.gather(). 3x asyncio.new_event_loop() anti-patterns fixed. enhanced_rag.py still on disk but no longer imported — delete in Phase 5.

#### Step 3.1: `rag/pipeline.py` (~150 lines)
- Move `enhanced_rag_query()` (line 1208) as the orchestrator
- Import from sibling modules instead of having everything inline
- Fix: run vector + BM25 search in parallel via `asyncio.gather()`

```python
async def enhanced_rag_query(query, sources, top_k=5, use_hybrid=True, use_cache=True):
    # 1. Check cache
    # 2. HyDE expansion (optional)
    # 3. Parallel search: asyncio.gather(vector_search(), bm25_search())
    # 4. RRF fusion
    # 5. Rerank
    # 6. Generate answer
    # 7. Cache result
```

#### Step 3.2: `rag/bm25.py` (~150 lines)
- Move `BM25Indexer` class (line 553-668)
- **Critical fix**: Replace full-collection load at startup with incremental indexing
- Use `infrastructure.milvus_client` instead of direct pymilvus

```python
class BM25Indexer:
    async def initialize(self, collection_name: str):
        # Incremental: only load new docs since last index
        # Use milvus_client.get_collection() instead of direct pymilvus

    async def search(self, query: str, top_k: int) -> list[dict]:
        # BM25 scoring
```

#### Step 3.3: `rag/reranker.py` (~120 lines)
- Move `Reranker` class (line 787-951)
- Use `infrastructure.llm_client` singleton instead of creating new client per call

#### Step 3.4: `rag/hyde.py` (~80 lines)
- Move `HyDEQueryExpander` class (line 953-1037)
- Use `infrastructure.llm_client` singleton

#### Step 3.5: `rag/fusion.py` (~50 lines)
- Move `reciprocal_rank_fusion()` function
- Pure function, no dependencies

#### Step 3.6: Move cache classes to `infrastructure/cache.py`
- `QueryCache` (line 96-134) → in-memory LRU
- `RedisQueryCache` (line 142-354) → Redis-backed
- Fix cache key: include `sources` + `top_k` in hash

**Verification**: `POST /api/v1/rag/query` returns correct results, cache hit/miss works.

---

### Phase 4: Service Layer Extraction (Day 5)

**Goal**: Routers become thin HTTP handlers. Business logic in services.

#### Step 4.1: `services/chat_service.py` (~100 lines)
```python
class ChatService:
    def __init__(self, storage: PostgreSQLConversationStorage, config: ConfigManager):
        self.storage = storage
        self.config = config

    async def list_chats(self) -> list[str]: ...
    async def create_chat(self) -> dict: ...
    async def get_current_chat(self) -> dict: ...
    async def delete_chat(self, chat_id: str) -> bool: ...
    async def rename_chat(self, chat_id: str, title: str) -> dict: ...
    async def clear_all(self) -> int: ...
```

#### Step 4.2: `services/rag_service.py` (~80 lines)
Thin wrapper around `rag.pipeline`:
```python
class RagService:
    async def query(self, query, sources, top_k, use_hybrid, use_cache) -> dict: ...
    async def get_stats(self) -> dict: ...
    async def get_config(self) -> dict: ...
    async def clear_cache(self) -> dict: ...
    async def get_cache_stats(self) -> dict: ...
```

#### Step 4.3: `services/knowledge_service.py` (~120 lines)
Extract knowledge sync logic from main.py:1346-1640:
```python
class KnowledgeService:
    async def get_status(self) -> dict: ...       # was 100+ lines inline
    async def sync(self, sources: list) -> dict: ...
    async def delete_source(self, name: str) -> dict: ...
```

#### Step 4.4: `services/ingest_service.py` (~60 lines)
Move `process_and_ingest_files_background()` from utils.py + ingest logic from main.py.

#### Step 4.5: `services/health_service.py` (~60 lines)
Aggregate health checks (postgres, milvus, agent, rag).

**Verification**: All endpoints return same responses as before. `pytest ../tests/ -v` green.

---

### Phase 5: Agent Decomposition + Cleanup (Day 6)

**Goal**: Slim agent.py from 791 → ~300 lines. Remove dead code.

#### Step 5.1: Extract from agent.py

| Extract To | What | Lines Saved |
|---|---|---|
| `infrastructure/observability.py` | Langfuse trace/span creation, callback handler | ~100 |
| `infrastructure/llm_client.py` | Model client creation, API type switching | ~80 |
| `agent.py` (keep) | ChatAgent core: StateGraph, query(), streaming | ~300 |

Key changes:
- `memory = MemorySaver()` → inject via `dependencies/providers.py`
- Module-level env var constants → read from `config.py`
- MCP tool init with retry → keep in agent but use `infrastructure.llm_client`

#### Step 5.2: Expand `models.py`
Move all inline `BaseModel` definitions from main.py into models.py:
- `RagQueryRequest` (main.py:494)
- `ChatRenameRequest` (main.py:689, duplicated!)
- Any other request/response models scattered in route handlers

#### Step 5.3: Dead Code Removal
- Delete `vector_store.py` if fully replaced by `infrastructure/milvus_client.py` + `rag/` modules
  - Or slim it to only the LangChain document loading/splitting logic
- Remove `utils.py` if `process_and_ingest_files_background()` moved to `services/ingest_service.py`
- Remove duplicate `ChatRenameRequest` definition

#### Step 5.4: Response Format Standardization
All endpoints must return:
```python
# Success
{"data": {...}}

# Error (RFC 7807 via errors.py)
{"error": {"code": "NOT_FOUND", "message": "...", "details": {...}}}
```
Replace all raw `HTTPException` raises with `errors.py` helpers.

---

## 5. Critical Bugs to Fix During Refactoring

These are from CODE_REVIEW.md and RAG_ANALYSIS.md — fix them as part of the relevant phase.

| Bug | Severity | Fix In Phase |
|---|---|---|
| `Qwen3Embedding` uses sync `requests` — blocks event loop | HIGH | Phase 1 (embedding_client.py) |
| `_generate_answer_with_llm()` creates new OpenAI client per call | HIGH | Phase 1 (llm_client.py) |
| `BM25Indexer.initialize()` loads entire Milvus collection | HIGH | Phase 3 (bm25.py) |
| `hybrid_search()` runs vector + BM25 sequentially | MEDIUM | Phase 3 (pipeline.py) |
| Cache key doesn't include sources/top_k → stale hits | MEDIUM | Phase 1 (cache.py) |
| 7+ scattered direct pymilvus imports | MEDIUM | Phase 1 (milvus_client.py) |
| 5 global variables | MEDIUM | Phase 1 (providers.py) |
| Duplicate `ChatRenameRequest` definition | LOW | Phase 5 (models.py) |

---

## 6. Critical Review of CODE_REVIEW.md Recommendations

### Accepted
- Router split (9 routers) — fully adopted
- Infrastructure layer — fully adopted
- DI via Depends() — fully adopted
- Response format standardization — adopted
- Legacy route removal — **exceeded**: we delete ALL legacy, not just deprecate

### Modified
- CODE_REVIEW suggests keeping legacy routes with deprecation headers → **Rejected**: clean break, no backward compat
- CODE_REVIEW suggests `services/` as optional Phase 2 → **Promoted to Phase 4**: services are essential for testability
- CODE_REVIEW rates MCP 0/10 and suggests MCP skill publishing → **Deferred**: out of scope for this refactor

### Rejected
- CODE_REVIEW suggests adding OpenTelemetry tracing → **Deferred**: Langfuse v2 is sufficient for now
- CODE_REVIEW suggests Redis-based rate limiting → **Deferred**: slowapi is adequate

---

## 7. Critical Review of RAG_ANALYSIS.md Recommendations

### Accepted
- Split enhanced_rag.py into rag/ modules — fully adopted
- Fix sync Qwen3Embedding → async httpx — adopted in Phase 1
- Fix sequential hybrid search → asyncio.gather — adopted in Phase 3
- Fix cache key to include sources — adopted in Phase 1
- Singleton LLM client — adopted in Phase 1

### Modified
- RAG_ANALYSIS suggests semantic chunking per document type → **Deferred**: requires significant testing, do after refactor
- RAG_ANALYSIS suggests incremental BM25 indexing → **Adopted but simplified**: track last-indexed timestamp, not full delta sync

### Rejected
- RAG_ANALYSIS suggests replacing BM25 with SPLADE → **Rejected**: BM25 works well enough, SPLADE adds model dependency
- RAG_ANALYSIS suggests multi-index Milvus strategy → **Deferred**: premature optimization

---

## 8. File Change Summary

| File | Before | After (Actual) | Delta | Status |
|------|--------|----------------|-------|--------|
| main.py | 2279 | 230 | -2049 | ✅ Done |
| agent.py | 791 | 791 (unchanged) | 0 | Phase 5 |
| enhanced_rag.py | 1381 | 1381 (orphaned) | 0 | Phase 5 delete |
| vector_store.py | 807 | 807 (unchanged) | 0 | Phase 5 |
| routers/ (11 files) | 0 | ~2151 | +2151 | ✅ Done |
| services/ (1 file) | 0 | 2 (placeholder) | +2 | Phase 4 |
| infrastructure/ (5 files) | 0 | ~517 | +517 | ✅ Done |
| rag/ (6 files) | 0 | ~978 | +978 | ✅ Done |
| dependencies/ (2 files) | 0 | ~72 | +72 | ✅ Done |
| **Total new code** | **0** | **~3950** | **+3950** | Phases 1-3 |

**Phases 1-3 complete.** main.py reduced from 2279→230 lines. New modular packages created.
Phases 4-5 will extract services, slim agent.py, and delete orphaned files (enhanced_rag.py, vector_store.py).

---

## 9. Verification Checklist (after each phase)

- [ ] `curl http://localhost:8000/api/v1/health` returns 200
- [ ] `pytest ../tests/ -v` all green
- [ ] No legacy routes respond (all return 404)
- [ ] No direct `pymilvus` imports outside `infrastructure/milvus_client.py`
- [ ] No global variables in main.py
- [ ] `main.py` < 150 lines
- [ ] All responses use `{"data": ...}` envelope

---

## SESSION_ID (for /ccg:execute use)
- CODEX_SESSION: N/A (codeagent-wrapper unavailable)
- GEMINI_SESSION: N/A (codeagent-wrapper unavailable)
