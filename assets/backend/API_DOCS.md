# Multi-Agent Chatbot 后端接口文档

> 版本: 1.3.0  
> 更新日期: 2026-02-24  
> 基础 URL: `http://localhost:8000`
> ⚠️ 此文档基于代码底层实现，请以实际代码为准

---

## ⚠️ 重要提示：接口选择指南

### 推荐：使用 RESTful API v1

我们提供两套接口：
1. **RESTful API v1** (推荐) - 符合业界最佳实践
2. **旧接口** (兼容) - 保留向后兼容

> **前端开发人员请使用 RESTful API v1**，旧接口仅用于兼容现有系统。

### 接口数量统计

| 接口类型 | 数量 | 状态 |
|---------|------|------|
| RESTful API v1 | 15 | ✅ 推荐使用 |
| OpenAI 兼容 API | 4 | ✅ 标准兼容 |
| WebSocket | 1 | ✅ 实时通信 |
| 健康检查/监控 | 6 | ✅ 完整支持 |
| LlamaIndex RAG | 5 | ✅ 增强功能 |
| 管理员接口 | 7 | ✅ 完整支持 |
| 旧接口 (兼容) | 27 | ⚠️ 维护中 |

---

## 目录

1. [RESTful API v1 (推荐)](#1-restful-api-v1-推荐)
2. [健康检查与监控](#2-健康检查与监控)
3. [RAG 查询接口](#3-rag-查询接口)
4. [OpenAI 兼容 API](#4-openai-兼容-api)
5. [WebSocket 实时通信](#5-websocket-实时通信)
6. [旧接口 (兼容)](#6-旧接口-兼容)
7. [错误响应格式](#7-错误响应格式)

---

## 1. RESTful API v1 (推荐)

> 符合 RESTful 规范的新接口，使用 `/api/v1` 前缀

### 1.1 会话管理

| 方法 | 路径 | 说明 | 代码位置 |
|------|------|------|----------|
| GET | `/api/v1/chats` | 获取所有会话 | main.py:563 |
| POST | `/api/v1/chats` | 创建新会话 | main.py:575 |
| DELETE | `/api/v1/chats` | 清除所有会话 | main.py:657 |
| GET | `/api/v1/chats/current` | 获取当前会话 | main.py:602 |
| PATCH | `/api/v1/chats/current` | 更新当前会话 | main.py:624 |
| GET | `/api/v1/chats/{chat_id}/messages` | 获取会话消息 | main.py:644 |
| GET | `/api/v1/chats/{chat_id}/metadata` | 获取会话元数据 | main.py:667 |
| PATCH | `/api/v1/chats/{chat_id}/metadata` | 更新会话元数据 | main.py:680 |
| DELETE | `/api/v1/chats/{chat_id}` | 删除指定会话 | main.py:697 |

#### 获取所有会话

**GET /api/v1/chats**

```bash
curl -X GET http://localhost:8000/api/v1/chats
```

**响应**:
```json
{
  "data": ["chat-id-1", "chat-id-2", ...]
}
```

#### 创建新会话

**POST /api/v1/chats**

```bash
curl -X POST http://localhost:8000/api/v1/chats
```

**响应**:
```json
{
  "data": {
    "chat_id": "new-chat-uuid",
    "message": "New chat created"
  }
}
```

#### 获取当前会话

**GET /api/v1/chats/current`

```bash
curl -X GET http://localhost:8000/api/v1/chats/current
```

**响应**:
```json
{
  "data": {
    "chat_id": "current-chat-uuid"
  }
}
```

#### 更新当前会话

**PATCH /api/v1/chats/current**

```bash
curl -X PATCH http://localhost:8000/api/v1/chats/current \
  -H "Content-Type: application/json" \
  -d '{"chat_id": "target-chat-uuid"}'
```

**响应**:
```json
{
  "data": {
    "chat_id": "target-chat-uuid",
    "message": "Current chat updated to target-chat-uuid"
  }
}
```

#### 获取会话消息

**GET /api/v1/chats/{chat_id}/messages**

```bash
curl -X GET "http://localhost:8000/api/v1/chats/{chat_id}/messages?limit=10"
```

**响应**:
```json
{
  "data": [
    {"type": "HumanMessage", "content": "你好"},
    {"type": "AIMessage", "content": "有什么可以帮你的？"}
  ]
}
```

#### 获取会话元数据

**GET /api/v1/chats/{chat_id}/metadata**

```bash
curl -X GET http://localhost:8000/api/v1/chats/{chat_id}/metadata
```

**响应**:
```json
{
  "data": {
    "name": "Chat Title",
    "created_at": "2026-01-01T00:00:00"
  }
}
```

#### 更新会话元数据（重命名）

**PATCH /api/v1/chats/{chat_id}/metadata**

```bash
curl -X PATCH http://localhost:8000/api/v1/chats/{chat_id}/metadata \
  -H "Content-Type: application/json" \
  -d '{"title": "新名称"}'
```

**响应**:
```json
{
  "data": {
    "chat_id": "chat-uuid",
    "title": "新名称",
    "message": "Chat metadata updated"
  }
}
```

#### 删除指定会话

**DELETE /api/v1/chats/{chat_id}**

```bash
curl -X DELETE http://localhost:8000/api/v1/chats/{chat_id}
```

**响应**:
```json
{
  "data": {
    "chat_id": "chat-uuid",
    "message": "Chat deleted successfully"
  }
}
```

#### 清除所有会话

**DELETE /api/v1/chats**

```bash
curl -X DELETE http://localhost:8000/api/v1/chats
```

**响应**:
```json
{
  "data": {
    "deleted_count": 10,
    "message": "Successfully deleted 10 chats"
  }
}
```

---

## 2. 健康检查与监控

> 用于基础设施监控和调试

| 方法 | 路径 | 说明 | 代码位置 |
|------|------|------|----------|
| GET | `/health` | 全局健康检查 (6 服务) | main.py:147 |
| GET | `/health/rag` | RAG 专项健康检查 | main.py:230 |
| GET | `/metrics` | 系统性能指标 | main.py:285 |
| GET | `/debug/config` | 调试: 当前配置 | main.py:336 |
| POST | `/debug/rebuild-bm25` | 调试: 重建 BM25 索引 | main.py:348 |
| GET | `/rag/llamaindex/cache/stats` | 查询缓存统计 | main.py:1821 |

#### 全局健康检查 - GET /health

检查 6 个基础设施服务状态：

```bash
curl -s http://localhost:8000/health
```

**响应**:
```json
{
  "status": "healthy",
  "timestamp": 1700000000.0,
  "services": {
    "postgres": "healthy",
    "milvus": "healthy",
    "embedding": "healthy",
    "llm": "healthy",
    "langfuse": "healthy",
    "redis": "healthy"
  }
}
```

**检查的服务**:
| 服务 | 检查方式 | 失败影响 |
|------|----------|----------|
| PostgreSQL | 连接池初始化 | degraded |
| Milvus | collection 存在性 | degraded |
| Embedding | /v1/embeddings 调用 | degraded |
| LLM | /v1/models 调用 | degraded |
| Langfuse | /api/health 调用 | - |
| Redis | ping + 降级检测 | 使用内存 |

#### RAG 健康检查 - GET /health/rag

```bash
curl -s http://localhost:8000/health/rag
```

**响应**:
```json
{
  "status": "healthy",
  "rag_index": {
    "collection": "context",
    "milvus_uri": "http://milvus:19530",
    "embedding_dimensions": 2560,
    "total_entities": 动态查询
  },
  "knowledge": {
    "config_sources": 38,
    "file_sources": 38,
    "vector_sources": 38,
    "fully_synced_count": 38,
    "issues": {}
  },
  "cache": {
    "backend": "redis",
    "ttl": 3600,
    "redis_available": true,
    "redis_keys": 5
  },
  "bm25_index": {
    "initialized": true,
    "document_count": 动态
  }
}
```

#### 系统性能指标 - GET /metrics

```bash
curl -s http://localhost:8000/metrics
```

**响应**:
```json
{
  "timestamp": 1700000000.0,
  "milvus": {
    "total_entities": 428,
    "index_count": 1
  },
  "conversations": {
    "total": 5
  },
  "rag_cache": {
    "cached_queries": 3,
    "ttl": 3600
  }
}
```

---

## 3. RAG 查询接口

### 3.1 增强 RAG 查询 (推荐)

| 方法 | 路径 | 说明 | 代码位置 |
|------|------|------|----------|
| POST | `/rag/llamaindex/query` | 增强 RAG 查询 | main.py:1751 |
| GET | `/rag/llamaindex/stats` | RAG 统计信息 | main.py:1780 |
| GET | `/rag/llamaindex/config` | RAG 配置信息 | main.py:1724 |
| POST | `/rag/llamaindex/cache/clear` | 清除查询缓存 | main.py:1803 |
| GET | `/rag/llamaindex/cache/stats` | 查询缓存统计 | main.py:1821 |

#### 增强 RAG 查询 - POST /rag/llamaindex/query

**完整参数** (基于 LlamaIndexQueryRequest):
```python
class LlamaIndexQueryRequest(BaseModel):
    query: str                      # 用户查询 (必填)
    sources: Optional[List[str]]    # 源过滤
    use_cache: bool = True         # 使用缓存 (默认开启)
    top_k: int = 10               # 检索数量
    use_hybrid: bool = True       # 混合搜索 BM25+Vector (默认开启)
    use_reranker: bool = True     # 重排序 (默认开启)
    rerank_top_k: int = 5         # 重排后返回数量
    use_hyde: bool = False        # HyDE 查询扩展 (默认关闭)
```

**请求示例**:
```bash
curl -X POST http://localhost:8000/rag/llamaindex/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "新加坡EP薪资要求",
    "top_k": 10,
    "use_hybrid": true,
    "use_reranker": true,
    "rerank_top_k": 5,
    "use_hyde": false
  }'
```

**响应**:
```json
{
  "answer": "根据检索到的文档...",
  "sources": [
    {
      "name": "新加坡就业准证EP与COMPASS完整指南_MOM.md",
      "score": 0.85,
      "vector_score": 0.92,
      "bm25_score": 0.78,
      "excerpt": "..."
    }
  ],
  "num_sources": 5,
  "search_type": "hybrid+reranked",
  "reranking_enabled": true,
  "hyde_applied": false
}
```

**工作流程**:
```
用户查询
    ↓
1. HyDE 扩展 (可选): 生成假设文档 → 提升长尾查询效果
    ↓
2. 查询缓存检查 (Redis + Memory 降级)
    ↓
3. 混合搜索:
   ├─→ milvus_query() → Qwen3 Embedding (2560维) → Milvus Vector Search
   └─→ bm25_query() → BM25 Full-Text Search
    ↓
4. RRF 融合 (k=60): 融合向量和 BM25 结果
    ↓
5. Cross-Encoder 重排序 (可选): 提升检索精度 15-25%
    ↓
6. LLM 生成答案 (gpt-oss-120b)
    ↓
7. 写入缓存 (Redis 持久化)
    ↓
返回结果
```

#### RAG 统计 - GET /rag/llamaindex/stats

```bash
curl -s http://localhost:8000/rag/llamaindex/stats
```

**响应**:
```json
{
  "index": {
    "collection": "context",
    "milvus_uri": "http://milvus:19530",
    "embedding_dimensions": 2560,
    "total_entities": 428
  },
  "cache": {
    "enabled": true,
    "backend": "redis",
    "redis_available": true,
    "ttl": 3600,
    "cached_queries": 5
  }
}
```

#### RAG 配置 - GET /rag/llamaindex/config

```bash
curl -s http://localhost:8000/rag/llamaindex/config
```

**响应**:
```json
{
  "status": "available",
  "features": {
    "hybrid_search": true,
    "multiple_chunking": true,
    "query_cache": true,
    "custom_embeddings": true
  },
  "chunk_strategies": ["auto", "semantic", "fixed", "code", "markdown"],
  "default_chunk_strategy": "auto",
  "default_top_k": 10
}
```

#### 清除缓存 - POST /rag/llamaindex/cache/clear

```bash
curl -X POST http://localhost:8000/rag/llamaindex/cache/clear
```

**响应**:
```json
{
  "status": "success",
  "message": "Query cache cleared (both Redis and memory)"
}
```

#### 缓存统计 - GET /rag/llamaindex/cache/stats

```bash
curl -s http://localhost:8000/rag/llamaindex/cache/stats
```

**响应**:
```json
{
  "status": "success",
  "memory_cache": {
    "entries": 2,
    "ttl": 3600
  },
  "redis_cache": {
    "backend": "redis",
    "ttl": 3600,
    "memory_entries": 0,
    "redis_available": true,
    "redis_keys": 5
  }
}
```

### 3.2 RESTful v1 RAG 接口

| 方法 | 路径 | 说明 | 代码位置 |
|------|------|------|----------|
| POST | `/api/v1/rag/query` | RAG 查询 (简化版) | main.py:484 |
| GET | `/api/v1/rag/stats` | RAG 统计信息 | main.py:502 |
| GET | `/api/v1/rag/config` | RAG 配置信息 | main.py:510 |

#### RAG 查询 (简化版) - POST /api/v1/rag/query

```bash
curl -X POST http://localhost:8000/api/v1/rag/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "新加坡EP薪资要求",
    "top_k": 5,
    "use_hybrid": true,
    "use_cache": true
  }'
```

**响应**:
```json
{
  "data": {
    "answer": "...",
    "sources": [...],
    "num_sources": 3,
    "search_type": "hybrid"
  }
}
```

### 3.3 知识库管理

| 方法 | 路径 | 说明 | 代码位置 |
|------|------|------|----------|
| GET | `/knowledge/status` | 知识库三层同步检查 | main.py:1078 |
| POST | `/knowledge/sync` | 同步知识库 | main.py:1175 |
| DELETE | `/knowledge/sources/{source_name}` | 删除知识源 | main.py:1257 |
| GET | `/sources/vector-counts` | 各源向量计数 | main.py:858 |

#### 知识库状态 - GET /knowledge/status

**三层检查**: Config → Files → Vectors

```bash
curl -s http://localhost:8000/knowledge/status
```

**响应**:
```json
{
  "status": "ok",
  "config": {
    "total": 38,
    "selected": 38,
    "sources": ["doc1.md", "doc2.pdf", ...]
  },
  "files": {
    "total": 38,
    "sources": ["doc1.md", "doc2.pdf", ...]
  },
  "vectors": {
    "total": 428,
    "sources": ["doc1.md", "doc2.pdf", ...]
  },
  "issues": {
    "orphaned_in_config": [],
    "untracked_files": [],
    "need_indexing": [],
    "orphaned_vectors": [],
    "config_without_vectors": []
  },
  "summary": {
    "config_files_match": true,
    "files_indexed": true,
    "vectors_clean": true,
    "fully_synced_count": 38,
    "config_has_vectors": true
  }
}
```

#### 向量计数 - GET /sources/vector-counts

```bash
curl -s http://localhost:8000/sources/vector-counts
```

**响应**:
```json
{
  "sources": ["doc1.md", "doc2.pdf", ...],
  "total_vectors": 428,
  "source_vectors": {
    "doc1.md": 15,
    "doc2.pdf": 23,
    ...
  },
  "status": "ready"
}
```

### 3.4 知识源管理

| 方法 | 路径 | 说明 | 代码位置 |
|------|------|------|----------|
| GET | `/api/v1/sources` | 获取所有文档源 | main.py:527 |
| POST | `/api/v1/sources:reindex` | 重新索引 | main.py:535 |
| GET | `/api/v1/selected-sources` | 获取选中的源 | main.py:551 |
| POST | `/api/v1/selected-sources` | 设置选中的源 | main.py:559 |
| GET | `/sources` | 获取所有源 (旧) | main.py:844 |
| POST | `/selected_sources` | 设置选中源 (旧) | main.py:1028 |

---

## 4. OpenAI 兼容 API

> 符合 OpenAI API 标准，可与 LobeHub、LangChain 等前端兼容

前缀: `/v1`

### 4.1 获取模型列表

**GET /v1/models**

```bash
curl http://localhost:8000/v1/models
```

**响应**:
```json
{
  "object": "list",
  "data": [
    {
      "id": "gpt-oss-120b",
      "object": "model",
      "created": 1700000000,
      "owned_by": "local",
      "permission": [],
      "root": "gpt-oss-120b"
    },
    {
      "id": "qwen3-embedding",
      "object": "model",
      "created": 1700000000,
      "owned_by": "local"
    }
  ]
}
```

### 4.2 聊天完成 (流式 SSE)

**POST /v1/chat/completions**

**请求**:
```bash
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "gpt-oss-120b",
    "messages": [{"role": "user", "content": "你好"}],
    "stream": true,
    "max_tokens": 16384
  }'
```

**响应** (SSE 流式):
```
data: {"choices":[{"delta":{"content":"你"},"index":0,"finish_reason":null}]}

data: {"choices":[{"delta":{"content":"好"},"index":0,"finish_reason":null}]}

data: [DONE]
```

### 4.3 创建嵌入向量

**POST /v1/embeddings**

**请求**:
```bash
curl -X POST http://localhost:8000/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen3-embedding",
    "input": "要嵌入的文本"
  }'
```

**响应**:
```json
{
  "object": "embedding",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.123, -0.456, ...],
      "index": 0
    }
  ],
  "model": "qwen3-embedding",
  "usage": {
    "prompt_tokens": 10,
    "total_tokens": 10
  }
}
```

> ⚠️ **注意**: Qwen3 Embedding 输出维度为 **2560 维** (实测)

---

## 5. WebSocket 实时通信

**端点**: `WS /ws/chat/{chat_id}?token=xxx&heartbeat=30`

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chat_id | string | 是 | 会话 ID |
| token | string | 否 | JWT 认证 token (AUTH_ENABLED 时必填) |
| heartbeat | int | 否 | 心跳间隔秒数 (默认 30, 范围 10-300) |

### 连接示例

```javascript
const ws = new WebSocket(
  'ws://localhost:8000/ws/chat/your-chat-id?heartbeat=30'
);

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case 'history':     // 消息历史
      console.log('历史消息:', msg.messages);
      break;
    case 'token':       // 流式 token
      process.stdout.write(msg.data);
      break;
    case 'tool_token':  // 工具输出
      console.log('工具输出:', msg.data);
      break;
    case 'node_start':  // 节点开始
      console.log('开始节点:', msg.data);
      break;
    case 'node_end':    // 节点结束
      console.log('结束节点:', msg.data);
      break;
    case 'tool_start':  // 工具开始
      console.log('开始工具:', msg.data);
      break;
    case 'tool_end':    // 工具结束
      console.log('结束工具:', msg.data);
      break;
    case 'ping':        // 心跳请求
      ws.send(JSON.stringify({ 
        type: 'pong', 
        timestamp: msg.timestamp 
      }));
      break;
    case 'stopped':     // 生成已停止
      console.log('生成已停止');
      break;
    case 'error':       // 错误
      console.error('错误:', msg.content);
      break;
  }
};

// 发送消息
ws.send(JSON.stringify({ message: '你好' }));

// 停止生成
ws.send(JSON.stringify({ type: 'stop' }));

// 发送图片 (需要先上传获取 image_id)
ws.send(JSON.stringify({ 
  message: '请分析这张图片',
  image_id: 'image-uuid'
}));
```

### 错误码

| 码 | 说明 | 代码位置 |
|----|------|----------|
| 4001 | 认证失败 | main.py:713 |
| 4002 | 心跳超时 | main.py:548 |
| 4003 | 无效的 chat_id | main.py:717 |

### 心跳机制

- **发送间隔**: 默认 30 秒 (可配置 10-300 秒)
- **超时检测**: 3 倍间隔无响应则断开 (默认 90 秒)
- **客户端要求**: 收到 `ping` 需回复 `pong`

---

## 6. 旧接口 (兼容)

> ⚠️ 以下接口已弃用，仅保留向后兼容，**不推荐使用**

### 6.1 会话管理

| 方法 | 路径 | 推荐替代 |
|------|------|---------|
| GET | `/chats` | GET `/api/v1/chats` |
| GET | `/chat_id` | GET `/api/v1/chats/current` |
| POST | `/chat/new` | POST `/api/v1/chats` |
| POST | `/chat/rename` | PATCH `/api/v1/chats/{id}/metadata` |
| DELETE | `/chat/{chat_id}` | DELETE `/api/v1/chats/{chat_id}` |
| DELETE | `/chats/clear` | DELETE `/api/v1/chats` |
| GET | `/chat/{chat_id}/metadata` | GET `/api/v1/chats/{chat_id}/metadata` |

### 6.2 知识库/RAG

| 方法 | 路径 | 推荐替代 |
|------|------|---------|
| GET | `/sources` | GET `/api/v1/sources` |
| POST | `/sources/reindex` | POST `/api/v1/sources:reindex` |
| GET | `/selected_sources` | GET `/api/v1/selected-sources` |
| POST | `/selected_sources` | POST `/api/v1/selected-sources` |

### 6.3 LlamaIndex RAG

| 方法 | 路径 | 推荐替代 |
|------|------|---------|
| GET | `/rag/llamaindex/config` | - (仍推荐使用) |
| POST | `/rag/llamaindex/query` | - (仍推荐使用) |
| GET | `/rag/llamaindex/stats` | - (仍推荐使用) |

### 6.4 管理员接口

| 方法 | 路径 |
|------|------|
| GET | `/admin/rag/stats` |
| GET | `/admin/rag/sources` |
| POST | `/admin/rag/sources/select` |
| POST | `/admin/rag/sources/select-all` |
| POST | `/admin/rag/sources/deselect-all` |
| GET | `/admin/conversations` |
| GET | `/admin/conversations/{chat_id}/messages` |

### 6.5 文件管理

| 方法 | 路径 |
|------|------|
| POST | `/upload-image` |
| POST | `/ingest` |
| GET | `/ingest/status/{task_id}` |

### 6.6 知识库

| 方法 | 路径 |
|------|------|
| GET | `/knowledge/status` |
| POST | `/knowledge/sync` |
| DELETE | `/knowledge/sources/{source_name}` |

### 6.7 其他

| 方法 | 路径 |
|------|------|
| GET | `/available_models` |
| GET | `/selected_model` |
| GET | `/test/rag` |
| GET | `/test/vector-stats` |
| DELETE | `/collections/{collection_name}` |
| DELETE | `/collections` |

---

## 7. 错误响应格式

> 所有 API 响应遵循统一格式 (遵循 RFC 7807)

### 成功响应

```json
{
  "data": { ... }
}
```

### 错误响应

```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "错误描述",
    "details": {}
  }
}
```

### 常见错误码

| 错误码 | HTTP 状态码 | 说明 | 定义位置 |
|--------|-------------|------|----------|
| `VALIDATION_ERROR` | 422 | 请求验证失败 | errors.py:13 |
| `UNAUTHORIZED` | 401 | 未认证 | errors.py:17 |
| `FORBIDDEN` | 403 | 禁止访问 | errors.py:18 |
| `NOT_FOUND` | 404 | 资源不存在 | errors.py:14 |
| `RATE_LIMIT_EXCEEDED` | 429 | 速率限制 | errors.py:22 |
| `INTERNAL_ERROR` | 500 | 内部错误 | errors.py:15 |
| `RAG_QUERY_ERROR` | 500 | RAG 查询错误 | errors.py:24 |
| `SOURCE_NOT_FOUND` | 404 | 源不存在 | errors.py:25 |
| `INDEXING_FAILED` | 500 | 索引失败 | errors.py:26 |

### 示例

**验证错误 (422)**:
```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "validation_errors": [
        {"field": "body.model", "message": "Field required", "type": "missing"}
      ]
    }
  }
}
```

**未找到 (404)**:
```json
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Chat 'xxx' not found",
    "details": {"resource": "Chat", "resource_id": "xxx"}
  }
}
```

**健康检查降级**:
```json
{
  "status": "degraded",
  "services": {
    "postgres": "healthy",
    "milvus": "unhealthy: Connection refused",
    "embedding": "healthy"
  }
}
```

---

## 快速参考

### 前端开发人员推荐工作流

1. **检查健康状态**: `GET /health`
2. **创建新会话**: `POST /api/v1/chats`
3. **获取当前会话**: `GET /api/v1/chats/current`
4. **实时聊天**: 使用 WebSocket `ws://localhost:8000/ws/chat/{chat_id}`
5. **获取历史**: `GET /api/v1/chats/{id}/messages`
6. **重命名**: `PATCH /api/v1/chats/{id}/metadata`
7. **删除**: `DELETE /api/v1/chats/{id}`

### RAG 查询推荐

```bash
# 基础查询 (使用默认优化)
curl -X POST http://localhost:8000/rag/llamaindex/query \
  -H "Content-Type: application/json" \
  -d '{"query": "新加坡EP薪资要求"}'

# 完整参数查询 (推荐)
curl -X POST http://localhost:8000/rag/llamaindex/query \
  -H "Content-Type: application/json" \
  -d '{
    "query": "新加坡EP薪资要求",
    "top_k": 10,
    "use_hybrid": true,
    "use_reranker": true,
    "rerank_top_k": 5,
    "use_hyde": true
  }'
```

### 模型选择

- 对话: 使用 `/v1/chat/completions` (OpenAI 兼容)
- Embedding: 使用 `/v1/embeddings` (Qwen3-Embedding, 2560维)
- RAG: 使用 `/rag/llamaindex/query` (增强版)

### 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODELS` | - | 可用模型列表 |
| `POSTGRES_HOST` | postgres | PostgreSQL 主机 |
| `REDIS_HOST` | localhost | Redis 主机 (缓存) |
| `SUPABASE_JWT_SECRET` | - | JWT 认证 (启用认证) |
| `LANGFUSE_PUBLIC_KEY` | - | Langfuse 可观测性 |

---

*此文档基于代码底层实现，最后更新: 2026-02-24*
*参考资料: main.py, enhanced_rag.py, agent.py, errors.py*
