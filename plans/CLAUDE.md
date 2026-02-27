# Claude Code 
# Multi-Agent Chatbot Backend - Claude Code Instructions

## 1. 重构路由文件

```python
"Migrate health check routes from main.py to app/routers/health.py"
```

## 3. 项目 CLAUDE.md 模板

```markdown
# Multi-Agent Chatbot Backend - Claude Code Instructions

## Project Overview
- Project: NVIDIA Multi-Agent Chatbot
- Location: assets/backend/
- Language: Python 3.11+
- Framework: FastAPI
- Target: Refactor main.py from 2280+ lines to <500 lines

## Architecture Rules

### R1. Single Responsibility
- main.py: Create app, register routers ONLY (<500 lines target)
- routers/: HTTP handling, delegate to services
- services/: Business logic ONLY  
- infrastructure/: External API wrappers ONLY

### R2. No Direct Infrastructure in Routers
FORBIDDEN: from pymilvus import connections
REQUIRED: from dependencies.providers import get_postgres_storage

### R3. API Conventions
- Use /api/v1/ prefix for all new endpoints
- Response format: {"data": {...}} or {"error": {"code": "...", "message": "..."}}

### R4. Dependency Injection
- Use FastAPI Depends() for all dependencies
- No global variables (agent, postgres_storage, vector_store)
- Use @lru_cache for singleton patterns

### R5. Import Order (PEP 8)
# 1. Standard library
# 2. Third-party  
# 3. Local application

## Current Refactoring Tasks

### Phase 1: Split Routers (Priority Order)
- [ ] health.py - /health, /health/rag, /metrics
- [ ] chats.py - All chat CRUD operations
- [ ] knowledge.py - /knowledge/* endpoints
- [ ] sources.py - /sources/* endpoints
- [ ] rag.py - /rag/*, /test/* endpoints
- [ ] admin.py - /admin/* endpoints
- [ ] config.py - /selected_*, /available_models
- [ ] debug.py - /debug/* endpoints
- [ ] upload.py - /upload-image, /ingest
- [ ] websocket.py - /ws/chat/*

### Phase 2: Extract Service Layer
- [ ] services/chat_service.py
- [ ] services/knowledge_service.py
- [ ] services/rag_service.py
- [ ] services/health_service.py

### Phase 3: Dependency Injection
- [ ] dependencies/providers.py

### Phase 4: Cleanup
- [ ] Remove all direct pymilvus imports from routers
- [ ] Verify main.py < 500 lines

## Commands

### Start Development
```bash
cd assets/backend
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### Test Endpoints
```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/v1/chats
```

### Run Tests
```bash
cd assets/backend
pytest tests/ -v
```

## Verification Checklist
After each task:
- [ ] Health check passes: curl http://localhost:8000/health
- [ ] Tests pass: pytest tests/ -v
- [ ] No new global variables introduced
- [ ] Main.py line count reduced

## Important Notes
- ALWAYS verify changes with tests
- Use Plan Mode for large refactors: claude --permission-mode plan
- Name sessions: /rename session-name
- Use /memory to save learnings
