# Multi-Agent Chatbot 后端接口文档

> 版本: 1.2.0  
> 更新日期: 2026-02-23  
> 基础 URL: `http://localhost:8000`

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
| RESTful API v1 | 11 | ✅ 推荐使用 |
| OpenAI 兼容 API | 4 | ✅ 标准兼容 |
| WebSocket | 1 | ✅ 实时通信 |
| 旧接口 (兼容) | 27 | ⚠️ 维护中 |

---

## 目录

1. [RESTful API v1 (推荐)](#1-restful-api-v1-推荐)
2. [OpenAI 兼容 API](#2-openai-兼容-api)
3. [WebSocket 实时通信](#3-websocket-实时通信)
4. [旧接口 (兼容)](#4-旧接口-兼容)
5. [错误响应格式](#5-错误响应格式)

---

## 1. RESTful API v1 (推荐)

> 符合 RESTful 规范的新接口，使用 `/api/v1` 前缀

### 1.1 会话管理

| 方法 | 路径 | 说明 | 替代旧接口 |
|------|------|------|-----------|
| GET | `/api/v1/chats` | 获取所有会话 | `/chats` |
| POST | `/api/v1/chats` | 创建新会话 | `/chat/new` |
| DELETE | `/api/v1/chats` | 清除所有会话 | `/chats/clear` |
| GET | `/api/v1/chats/current` | 获取当前会话 | `/chat_id` |
| PATCH | `/api/v1/chats/current` | 更新当前会话 | POST `/chat_id` |
| GET | `/api/v1/chats/{chat_id}/messages` | 获取会话消息 | - |
| GET | `/api/v1/chats/{chat_id}/metadata` | 获取会话元数据 | `/chat/{id}/metadata` |
| PATCH | `/api/v1/chats/{chat_id}/metadata` | 更新会话元数据 | POST `/chat/rename` |
| DELETE | `/api/v1/chats/{chat_id}` | 删除指定会话 | DELETE `/chat/{id}` |

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

### 1.2 知识源管理

| 方法 | 路径 | 说明 | 替代旧接口 |
|------|------|------|-----------|
| GET | `/api/v1/sources` | 获取所有文档源 | `/sources` |
| POST | `/api/v1/sources:reindex` | 重新索引 | `/sources/reindex` |
| GET | `/api/v1/selected-sources` | 获取选中的源 | `/selected_sources` |
| POST | `/api/v1/selected-sources` | 设置选中的源 | POST `/selected_sources` |

#### 获取所有文档源

**GET /api/v1/sources**

```bash
curl -X GET http://localhost:8000/api/v1/sources
```

**响应**:
```json
{
  "data": ["source1.pdf", "source2.md", ...]
}
```

#### 重新索引

**POST /api/v1/sources:reindex**

```bash
curl -X POST http://localhost:8000/api/v1/sources:reindex \
  -H "Content-Type: application/json" \
  -d '{"sources": ["source1.pdf"]}'
```

**响应**:
```json
{
  "data": {
    "task_id": "task-uuid",
    "status": "started"
  }
}
```

#### 获取选中的源

**GET /api/v1/selected-sources**

```bash
curl -X GET http://localhost:8000/api/v1/selected-sources
```

**响应**:
```json
{
  "data": ["source1.pdf", "source2.md"]
}
```

#### 设置选中的源

**POST /api/v1/selected-sources**

```bash
curl -X POST http://localhost:8000/api/v1/selected-sources \
  -H "Content-Type: application/json" \
  -d '{"sources": ["source1.pdf"]}'
```

**响应**:
```json
{
  "data": {
    "selected_sources": ["source1.pdf"]
  }
}
```

---

## 2. OpenAI 兼容 API

> 符合 OpenAI API 标准，可与 LobeHub、LangChain 等前端兼容

前缀: `/v1`

### 2.1 获取模型列表

**GET /v1/models**

**响应**:
```json
{
  "object": "list",
  "data": [
    {"id": "gpt-oss-120b", "object": "model", "created": 1700000000, "owned_by": "local"},
    {"id": "qwen3-embedding", "object": "model", "created": 1700000000, "owned_by": "local"}
  ]
}
```

### 2.2 聊天完成 (流式 SSE)

**POST /v1/chat/completions**

**请求**:
```json
{
  "model": "gpt-oss-120b",
  "messages": [{"role": "user", "content": "你好"}],
  "stream": true
}
```

**响应** (SSE 流式):
```
data: {"choices":[{"delta":{"content":"你"},"index":0}]}
data: {"choices":[{"delta":{"content":"好"},"index":0}]}
data: [DONE]
```

### 2.3 创建嵌入向量

**POST /v1/embeddings**

**请求**:
```json
{
  "model": "qwen3-embedding",
  "input": "要嵌入的文本"
}
```

---

## 3. WebSocket 实时通信

**端点**: `WS /ws/chat/{chat_id}?token=xxx&heartbeat=30`

### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| chat_id | string | 是 | 会话 ID |
| token | string | 否 | JWT 认证 token |
| heartbeat | int | 否 | 心跳间隔 (默认 30 秒) |

### 连接示例

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat/your-chat-id?heartbeat=30');

ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  switch (msg.type) {
    case 'history':     // 消息历史
    case 'token':       // 流式 token
    case 'tool_token':  // 工具输出
    case 'node_start':  // 节点开始
    case 'node_end':    // 节点结束
    case 'tool_start':  // 工具开始
    case 'tool_end':    // 工具结束
    case 'ping':        // 心跳请求
      ws.send(JSON.stringify({ type: 'pong', timestamp: msg.timestamp }));
      break;
    case 'stopped':     // 生成已停止
    case 'error':       // 错误
      break;
  }
};

// 发送消息
ws.send(JSON.stringify({ message: '你好' }));

// 停止生成
ws.send(JSON.stringify({ stop: true }));
```

### 错误码

| 码 | 说明 |
|----|------|
| 4001 | 认证失败 |
| 4002 | 心跳超时 |
| 4003 | 无效的 chat_id |

---

## 4. 旧接口 (兼容)

> ⚠️ 以下接口已弃用，仅保留向后兼容，**不推荐使用**

### 4.1 会话管理

| 方法 | 路径 | 推荐替代 |
|------|------|---------|
| GET | `/chats` | GET `/api/v1/chats` |
| GET | `/chat_id` | GET `/api/v1/chats/current` |
| POST | `/chat/new` | POST `/api/v1/chats` |
| POST | `/chat/rename` | PATCH `/api/v1/chats/{id}/metadata` |
| DELETE | `/chat/{chat_id}` | DELETE `/api/v1/chats/{chat_id}` |
| DELETE | `/chats/clear` | DELETE `/api/v1/chats` |
| GET | `/chat/{chat_id}/metadata` | GET `/api/v1/chats/{chat_id}/metadata` |

### 4.2 知识库/RAG

| 方法 | 路径 | 推荐替代 |
|------|------|---------|
| GET | `/sources` | GET `/api/v1/sources` |
| POST | `/sources/reindex` | POST `/api/v1/sources:reindex` |
| GET | `/selected_sources` | GET `/api/v1/selected-sources` |
| POST | `/selected_sources` | POST `/api/v1/selected-sources` |

### 4.3 LlamaIndex RAG

| 方法 | 路径 |
|------|------|
| GET | `/rag/llamaindex/config` |
| POST | `/rag/llamaindex/query` |
| GET | `/rag/llamaindex/stats` |
| POST | `/rag/llamaindex/cache/clear` |

### 4.4 管理员接口

| 方法 | 路径 |
|------|------|
| GET | `/admin/rag/stats` |
| GET | `/admin/rag/sources` |
| POST | `/admin/rag/sources/select` |
| POST | `/admin/rag/sources/select-all` |
| POST | `/admin/rag/sources/deselect-all` |
| GET | `/admin/conversations` |
| GET | `/admin/conversations/{chat_id}/messages` |

### 4.5 文件管理

| 方法 | 路径 |
|------|------|
| POST | `/upload-image` |
| POST | `/ingest` |
| GET | `/ingest/status/{task_id}` |

### 4.6 知识库

| 方法 | 路径 |
|------|------|
| GET | `/knowledge/status` |
| POST | `/knowledge/sync` |
| DELETE | `/knowledge/sources/{source_name}` |

### 4.7 其他

| 方法 | 路径 |
|------|------|
| GET | `/available_models` |
| GET | `/selected_model` |
| GET | `/test/rag` |
| GET | `/test/vector-stats` |
| DELETE | `/collections/{collection_name}` |
| DELETE | `/collections` |

---

## 5. 错误响应格式

> 所有 API 响应遵循统一格式

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

| 错误码 | HTTP 状态码 | 说明 |
|--------|-------------|------|
| `VALIDATION_ERROR` | 422 | 请求验证失败 |
| `UNAUTHORIZED` | 401 | 未认证 |
| `FORBIDDEN` | 403 | 禁止访问 |
| `NOT_FOUND` | 404 | 资源不存在 |
| `RATE_LIMIT_EXCEEDED` | 429 | 速率限制 |
| `INTERNAL_ERROR` | 500 | 内部错误 |

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

---

## 快速参考

### 前端开发人员推荐工作流

1. **创建新会话**: `POST /api/v1/chats`
2. **获取当前会话**: `GET /api/v1/chats/current`
3. **实时聊天**: 使用 WebSocket `ws://localhost:8000/ws/chat/{chat_id}`
4. **获取历史**: `GET /api/v1/chats/{id}/messages`
5. **重命名**: `PATCH /api/v1/chats/{id}/metadata`
6. **删除**: `DELETE /api/v1/chats/{id}`

### 模型选择

- 对话: 使用 `/v1/chat/completions` (OpenAI 兼容)
- Embedding: 使用 `/v1/embeddings` (OpenAI 兼容)
