# AGENTS.md

This file provides guidance to agents when working with code in this repository.

## Project

RAG-based multi-agent chatbot on DGX Spark (Grace Blackwell, 128GB unified memory).
- Backend: `assets/backend/` — Python 3.12, FastAPI + LangGraph + LlamaIndex
- Frontend: `assets/frontend/` — Next.js 14 (App Router)
- Infra: Docker Compose (`assets/docker-compose.yml`)

## Commands

```bash
# Backend (must run from assets/backend/ with venv active)
cd assets/backend && source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Single test file
cd assets/backend && pytest ../tests/test_api.py -v
# All tests
cd assets/backend && pytest ../tests/ -v

# Frontend
cd assets/frontend && pnpm dev   # port 3000

# Health check
curl http://localhost:8000/health
```

## Critical Non-Obvious Rules

### Backend Architecture
- `main.py` is 2280+ lines with 45+ routes — **currently being refactored** (see `plans/refactor_preparation_guide.md`)
- Target structure: `routers/` + `services/` + `infrastructure/` + `dependencies/`
- **FORBIDDEN**: `from pymilvus import connections` in routers — use `from dependencies.providers import get_milvus_client`
- **FORBIDDEN**: global variables (`agent`, `postgres_storage`, `vector_store`) — use FastAPI `Depends()`

### API Conventions
- All new endpoints: prefix `/api/v1/`
- Error format: `{"error": {"code": "ERROR_CODE", "message": "...", "details": {...}}}`
- Use `errors.py` helpers: `create_error_response()`, `not_found_error()`, etc. — never raw `HTTPException`

### Dependencies (Critical Versions)
- **Langfuse MUST be v2** (`>=2.0.0,<3.0.0`) — v3 has incompatible API (see `pyproject.toml` line 44)
- Package manager: `uv` (not pip) — `uv add <pkg>`, `uv sync`

### Configuration
- `config.json` is auto-created by `ConfigManager` at startup from `MODELS` env var
- Models loaded from `MODELS` env var (comma-separated): `MODELS=gpt-oss-120b,deepseek-coder`
- `LLM_API_TYPE=local|openai` controls whether to use local NIM or external API
- `LLM_BASE_URL` defaults to `http://gpt-oss-120b:8000/v1`

### Logging
- All logs are JSON-structured via `logger.py` — use `logger.info({"message": "...", "key": val})`
- Log file: `app.log` in backend working directory
- Import: `from logger import logger, log_request, log_response, log_error`

### Testing
- Tests live in `assets/tests/` (NOT in `assets/backend/tests/`)
- Tests use `requests` + `websockets` (not pytest fixtures) — run against live server
- `test_api.py --quick` for fast subset, `--v1` for REST only, `--rag` for RAG only

### Local Models (NIM on DGX Spark)
| Service | Host | Purpose |
|---------|------|---------|
| `gpt-oss-120b:8000` | Main LLM | MXFP4, ~63.5GB |
| `deepseek-coder:8000` | Code gen | Q8, ~9.5GB |
| `qwen3-embedding:8000` | Embeddings | Q8, ~5.39GB |
| `milvus:19530` | Vector DB | GPU-accelerated |
| `postgres:5432` | Chat storage | asyncpg |
| `redis:6379` | Query cache | TTL 6h |

### WebSocket
- Chat endpoint: `ws://localhost:8000/ws/chat/{chat_id}`
- Auth: optional JWT via `SUPABASE_JWT_SECRET` env var (disabled if not set)
