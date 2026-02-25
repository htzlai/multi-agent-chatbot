# RAG 专业领域知识库系统 - 原子级深度分析报告

> 分析日期: 2026-02-24 (原子级更新)
> 基于代码底层第一性原理分析
> ⚠️ 重要: 此文档反映代码底层实现，API 会持续演进请参考代码

---

## 一、系统架构全景 (原子级视角)

你的 RAG 系统是一个**六层架构**的专业领域知识库，每一层都是原子级别的独立组件：

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           用户交互层                                          │
│  ┌──────────────────┐  ┌──────────────────┐  ┌──────────────────────────┐  │
│  │  WebSocket       │  │  REST API        │  │  OpenAI 兼容接口        │  │
│  │  实时对话+心跳   │  │  文件摄取/RAG查询 │  │  /v1/* 端点            │  │
│  │  ws://host:8000 │  │  /ingest, /rag   │  │  openai_compatible/    │  │
│  └──────────────────┘  └──────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                        LangGraph Agent 层                                    │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │  ChatAgent (agent.py:51-109)                                        │   │
│  │  ├── LangGraph StateGraph + MemorySaver                             │   │
│  │  ├── MCP Tools 集成 (4个服务器)                                      │   │
│  │  │   ├── image-understanding-server (图像理解)                     │   │
│  │  │   ├── code-generation-server (代码生成)                         │   │
│  │  │   ├── rag-server (知识库检索)                                   │   │
│  │  │   └── weather-server (天气查询)                                 │   │
│  │  ├── Langfuse 可观测性集成                                         │   │
│  │  └── 实时流式输出 + stop_event 取消支持                             │   │
│  └──────────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      RAG 查询引擎层 (enhanced_rag.py)                       │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  enhanced_rag_query() - 主入口 (enhanced_rag.py:878-973)          │    │
│  │                                                                     │    │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │    │
│  │  │ HyDE 查询扩展   │→ │ Hybrid Search   │→ │ Cross-Encoder  │     │    │
│  │  │ (可选)         │  │ BM25+Vector+RRF│  │ Reranking      │     │    │
│  │  │ HyDEQueryExpander │  │ reciprocal_rank_fusion │  | Reranker    │     │    │
│  │  └─────────────────┘  └─────────────────┘  └─────────────────┘     │    │
│  │                                                                     │    │
│  │  ┌─────────────────────────────────────────────────────────────┐   │    │
│  │  │ Query Cache (Redis + Memory Fallback)                       │   │    │
│  │  │ RedisQueryCache: TTL, 持久化, 自动降级                      │   │    │
│  │  │ get_redis_query_cache(): 全局单例 (enhanced_rag.py:267)    │   │    │
│  │  └─────────────────────────────────────────────────────────────┘   │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                      向量存储层 (vector_store.py)                            │
│  ┌────────────────────────────────────────────────────────────────────┐    │
│  │  VectorStore 类 (vector_store.py:127-595)                         │    │
│  │                                                                     │    │
│  │  ┌────────────────────────────────────────────────────────────┐    │    │
│  │  │ CustomEmbeddings (vector_store.py:36-124)                  │    │    │
│  │  │ • Qwen3-Embedding-4B-Q8_0.gguf → 2560 维向量 (实测)        │    │    │
│  │  │ • ThreadPoolExecutor: 10 并发线程并行处理                   │    │    │
│  │  │ • 批处理支持 (batch_size=100)                              │    │    │
│  │  │ • Fallback 零向量: [0.0] * 2560                            │    │    │
│  │  └────────────────────────────────────────────────────────────┘    │    │
│  │                                                                     │    │
│  │  ┌────────────────────────────────────────────────────────────┐    │    │
│  │  │ 文档摄取流程 (_load_documents, vector_store.py:268-388)   │    │    │
│  │  │ 1. UnstructuredLoader → PyPDF fallback → raw text 兜底    │    │    │
│  │  │ 2. RecursiveCharacterTextSplitter                        │    │    │
│  │  │    chunk_size=512, chunk_overlap=128                     │    │    │
│  │  │ 3. 10线程并行 embedding                                    │    │    │
│  │  │ 4. Milvus collection: "context" (auto_id=True)            │    │    │
│  │  └────────────────────────────────────────────────────────────┘    │    │
│  └────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                         数据持久化层                                         │
│  ┌──────────────────┐  ┌──────────────────┐  ┌───────────────────────┐    │
│  │  Milvus         │  │  PostgreSQL      │  │  文件系统             │    │
│  │  (向量数据库)    │  │  (会话存储)       │  │  (/app/uploads/)     │    │
│  │  IP/L2 度量     │  │  asyncpg 连接池   │  │  source_mapping.json │    │
│  │  context collection│  │  JSONB 消息      │  │  原始文档存储        │    │
│  │  动态检测度量类型 │  │  缓存+批处理保存  │  │  task_id 追踪        │    │
│  └──────────────────┘  └──────────────────┘  └───────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                      ↓
┌─────────────────────────────────────────────────────────────────────────────┐
│                          基础设施层                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ MinIO        │  │ Redis        │  │ Langfuse     │  │ Supabase     │   │
│  │ (对象存储)    │  │ (查询缓存)    │  │ (可观测性)   │  │ (JWT认证)    │   │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘   │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、原子级代码分析 - 核心组件

### 2.1 main.py - FastAPI 应用核心 (约 1800+ 行)

**应用生命周期**:
```python
# main.py:72-99
@lifespan(app)
async def lifespan(app: FastAPI):
    """启动: PostgreSQL 初始化 → Agent 创建"""
    await postgres_storage.init_pool()  # 连接池初始化
    agent = await ChatAgent.create(...)  # 异步创建
    
    yield  # 运行中
    
    """关闭: 资源清理"""
    await postgres_storage.close()
```

**关键端点群**:

| 端点 | 方法 | 功能 | 代码位置 |
|------|------|------|----------|
| `/health` | GET | 全局健康检查 (6 服务) | main.py:147-228 |
| `/health/rag` | GET | RAG 专项健康检查 | main.py:230-283 |
| `/ws/chat/{chat_id}` | WebSocket | 实时对话 | main.py:685-757 |
| `/ingest` | POST | 文档摄取 | main.py:779-829 |
| `/knowledge/status` | GET | 知识库三层同步检查 | main.py:1078-1173 |
| `/rag/llamaindex/query` | POST | 增强 RAG 查询 | main.py:1751-1778 |
| `/rag/llamaindex/stats` | GET | RAG 统计 | main.py:1780-1801 |
| `/admin/rag/*` | * | 管理员功能 | main.py:1827-1905 |

**WebSocket 心跳机制** (main.py:534):
```python
heartbeat_interval = 30  # 心跳间隔秒数
heartbeat_timeout = 90   # 3倍间隔无响应则断开
# 客户端需回复 {"type": "pong"}
```

**统一错误处理** (main.py:149-242):
- APIError 自定义异常
- RequestValidationError Pydantic 验证错误
- HTTPException 转换
- 全局 Exception 捕获

---

### 2.2 agent.py - LangGraph 对话代理 (约 600+ 行)

**ChatAgent 类结构**:
```python
# agent.py:51-109
class ChatAgent:
    def __init__(self, vector_store, config_manager, postgres_storage):
        self.graph = self._build_graph()  # LangGraph StateGraph
        self.max_iterations = 3           # 最大工具调用次数
        self.mcp_client = None             # MCP 工具客户端
        self.openai_tools = []            # 转换后的 OpenAI 格式工具
        self.langfuse = get_langfuse_client()  # 可观测性
```

**LangGraph 状态机**:
```
START → generate (生成) → should_continue (判断) 
                                    ↓
                              ┌───────┴───────┐
                              ↓               ↓
                           "continue"       "end"
                              ↓               ↓
                         action (工具执行)    END
                              ↓
                         generate
```

**工具执行流程** (agent.py:175-227):
```python
async def tool_node(self, state: State):
    """执行工具调用"""
    for tool_call in last_message.tool_calls:
        # 特殊处理图像
        if tool_call["name"] == "explain_image" and state.get("image_data"):
            tool_result = await self.tools_by_name[tool_call["name"]].ainvoke(
                {**tool_call["args"], "image": state["image_data"]}
            )
        else:
            tool_result = await self.tools_by_name[tool_call["name"]].ainvoke(tool_call["args"])
```

**流式输出处理** (agent.py:294-365):
- `_stream_response()`: 处理 LLM 流式输出
- `_close_stream_connection()`: 主动关闭 HTTP 连接支持取消
- stop_event: 支持中断生成

---

### 2.3 enhanced_rag.py - 增强 RAG 引擎 (约 1000+ 行)

**核心类图**:

```
enhanced_rag.py
├── Qwen3Embedding (41-74)
│   └── 实测维度: 2560
│
├── QueryCache (93-123)
│   └── 内存缓存 (向后兼容)
│
├── RedisQueryCache (126-267)
│   ├── Redis 持久化 + 内存降级
│   ├── TTL 支持
│   └── get_redis_query_cache(): 全局单例
│
├── BM25Indexer (314-423)
│   ├── _tokenize(): 简单中英文分词
│   ├── initialize(): 从 Milvus 加载
│   └── search(): BM25 评分
│
├── Reranker (436-570)
│   ├── 外部服务支持
│   └── _rerank_simple(): 关键词重叠评分 (降级方案)
│
├── HyDEQueryExpander (583-656)
│   ├── expand_query(): 生成假设文档
│   └── expand_query_sync(): 同步版本
│
└── enhanced_rag_query() (878-973)
    ├── HyDE 扩展 (可选)
    ├── 混合搜索
    ├── RRF 融合
    ├── 重排序 (可选)
    └── 缓存
```

**混合搜索流程** (enhanced_rag.py:706-779):
```python
def hybrid_search(query, top_k=10, sources=None, ...):
    # 1. 向量搜索
    vector_result = milvus_query(query, top_k, sources)
    
    # 2. BM25 搜索
    bm25_result = bm25_query(query, top_k, sources)
    
    # 3. RRF 融合
    fused_sources = reciprocal_rank_fusion(vector_sources, bm25_sources, k=60)
    
    # 4. 可选重排序
    if use_reranker:
        final_sources = rerank_documents(query, fused_sources, rerank_top_k)
```

**RRF 融合公式** (enhanced_rag.py:362-407):
```
score = Σ 1/(k + rank)  for each result in both lists
k = 60 (标准参数)
```

**查询缓存** (enhanced_rag.py:126-267):
```python
class RedisQueryCache:
    def __init__(self, ttl=3600, use_redis=True, memory_fallback=True):
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        # 自动降级: Redis 不可用 → 内存缓存
```

---

### 2.4 vector_store.py - Milvus 向量存储 (约 600+ 行)

**CustomEmbeddings** (vector_store.py:36-124):
```python
class CustomEmbeddings:
    DEFAULT_EMBEDDING_DIMENSION = 2560  # Qwen3 实测维度
    
    def __init__(self, max_workers=10, batch_size=100):
        self.max_workers = 10  # 并发线程数
    
    def __call__(self, texts):
        """ThreadPoolExecutor 并行请求"""
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # 10 线程并行
```

**VectorStore 核心方法**:

| 方法 | 功能 | 代码位置 |
|------|------|----------|
| `_load_documents()` | 文档加载 + 文本提取 | vector_store.py:268-388 |
| `index_documents()` | 文本分块 + 向量化 + 存储 | vector_store.py:390-414 |
| `get_documents()` | 向量相似度检索 | vector_store.py:416-461 |
| `get_documents_with_scores()` | 带分数检索 | vector_store.py:463-565 |
| `delete_by_source()` | 按源删除向量 | vector_store.py:567-653 |

**文本提取优先级** (vector_store.py:300-340):
1. UnstructuredLoader (首选)
2. PyPDF (PDF 降级)
3. raw text read (兜底)

**分块配置** (vector_store.py:171-174):
```python
self.text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=512,    # 优化后
    chunk_overlap=128  # 约 25% chunk_size
)
```

---

### 2.5 postgres_storage.py - 会话存储 (约 500+ 行)

**PostgreSQLConversationStorage** 特性:

```python
class PostgreSQLConversationStorage:
    def __init__(self, cache_ttl=300, pool_size=10):
        # 三级缓存
        self._message_cache: Dict[str, CacheEntry]      # 消息缓存
        self._metadata_cache: Dict[str, CacheEntry]     # 元数据缓存
        self._image_cache: Dict[str, CacheEntry]         # 图像缓存
        
        # 批处理保存
        self._pending_saves: Dict[str, List[BaseMessage]]
        self._batch_save_task: asyncio.Task  # 后台批处理任务
```

**数据库表结构**:

```sql
-- conversations: 消息存储
CREATE TABLE conversations (
    chat_id VARCHAR(255) PRIMARY KEY,
    messages JSONB NOT NULL,           -- 消息 JSONB 存储
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    message_count INTEGER
);

-- chat_metadata: 会话元数据
CREATE TABLE chat_metadata (
    chat_id VARCHAR(255) PRIMARY KEY,
    name VARCHAR(500),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

-- images: 临时图像存储 (1小时 TTL)
CREATE TABLE images (
    image_id VARCHAR(255) PRIMARY KEY,
    image_data TEXT,                   -- Base64 编码
    expires_at TIMESTAMP               -- 1小时后自动过期
);
```

**缓存策略**:
- 消息缓存 TTL: 300 秒 (可配置)
- 元数据缓存 TTL: 300 秒
- 图像缓存 TTL: 3600 秒
- 自动批处理: 1 秒间隔

---

### 2.6 auth.py - JWT 认证 (约 120 行)

```python
# 支持 Supabase JWT 认证
SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET", "")

def verify_token(token: str) -> dict:
    """验证 JWT token (HS256)"""
    payload = jwt.decode(
        token,
        SUPABASE_JWT_SECRET,
        algorithms=["HS256"],
        options={"verify_aud": False, "verify_iss": False}
    )
    return payload
```

**WebSocket 认证**:
```python
# main.py:708-720
@app.websocket("/ws/chat/{chat_id}")
async def websocket_endpoint(websocket, chat_id, token: str = None):
    if AUTH_ENABLED:  # SUPABASE_JWT_SECRET 已配置
        user = verify_token(token)
```

---

### 2.7 errors.py - 统一错误处理 (约 200 行)

**错误码体系** (遵循 RFC 7807):
```python
class ErrorCode:
    # 通用
    UNKNOWN_ERROR = "UNKNOWN_ERROR"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    NOT_FOUND = "NOT_FOUND"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    
    # 认证
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    
    # RAG
    RAG_QUERY_ERROR = "RAG_QUERY_ERROR"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    INDEXING_FAILED = "INDEXING_FAILED"
```

---

### 2.8 client.py - MCP 工具客户端 (约 80 行)

**MCP 服务器配置**:
```python
self.server_configs = {
    "image-understanding-server": {
        "command": "python",
        "args": ["tools/mcp_servers/image_understanding.py"],
    },
    "code-generation-server": {...},
    "rag-server": {...},
    "weather-server": {...}
}
```

**初始化重试** (agent.py:113-135):
```python
for attempt in range(max_retries):
    try:
        mcp_tools = await self.mcp_client.get_tools()
        break
    except:
        wait_time = base_delay * (2 ** attempt)  # 指数退避
        await asyncio.sleep(wait_time)
```

---

## 三、接口工作原理深度解析

### 3.1 RAG 查询接口群

#### 📌 `POST /rag/llamaindex/query`

**完整参数**:
```python
class LlamaIndexQueryRequest(BaseModel):
    query: str                      # 用户查询
    sources: Optional[List[str]]    # 源过滤
    use_cache: bool = True          # 使用缓存
    top_k: int = 10                 # 检索数量
    use_hybrid: bool = True         # 混合搜索
    use_reranker: bool = True       # 重排序
    rerank_top_k: int = 5           # 重排后数量
    use_hyde: bool = False          # HyDE 扩展
```

**工作流程**:
```
用户查询
    ↓
1. HyDE 扩展 (可选): 生成假设文档
    ↓
2. 查询缓存检查 (Redis + Memory)
    ↓
3. 混合搜索:
   ├─→ milvus_query() → Qwen3 Embedding → Milvus Vector Search
   └─→ bm25_query() → BM25 Full-Text Search
    ↓
4. RRF 融合 (k=60)
    ↓
5. Cross-Encoder 重排序 (可选)
    ↓
6. LLM 生成答案
    ↓
7. 写入缓存
    ↓
返回结果
```

#### 📌 `GET /health/rag` - RAG 健康检查

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
    "vector_sources": 动态,
    "fully_synced_count": 动态,
    "issues": {}
  },
  "cache": {
    "backend": "redis" | "memory",
    "ttl": 3600,
    "redis_available": true | false
  },
  "bm25_index": {
    "initialized": true,
    "document_count": 动态
  }
}
```

---

### 3.2 知识库状态接口群

#### 📌 `GET /knowledge/status`

**三层检查**:
```
┌────────────────────────────────────────────────────────────┐
│  Layer 1: Config (config.json)                            │
│  • sources: 38 个配置的文档源                              │
│  • selected_sources: 38 个选中的源 (全部选中)            │
└────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────┐
│  Layer 2: Files (/app/uploads/)                          │
│  • total: 38 个上传的文档                                 │
│  • source_mapping.json 追踪                               │
└────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────┐
│  Layer 3: Vectors (Milvus)                              │
│  • total: 动态查询                                        │
│  • collection: "context"                                  │
└────────────────────────────────────────────────────────────┘
```

**同步状态分析**:
```python
# main.py:1124-1147
orphaned_in_config = config_sources - file_sources      # 配置有但文件无
untracked_files = file_sources - config_sources          # 文件有但配置无
need_indexing = file_sources - vector_sources             # 有文件但无向量
orphaned_vectors = vector_sources - file_sources         # 有向量但文件无
config_without_vectors = config_sources - vector_sources  # 配置有但向量无
fully_synced = config_sources & file_sources & vector_sources  # 全部同步
```

---

## 四、原子级深度洞察

### 架构洞察

1. **六层清晰分离**: 用户交互 → Agent → RAG引擎 → 向量存储 → 持久化 → 基础设施

2. **LangGraph 状态机**: 使用 `should_continue` 条件边实现工具循环调用

3. **MCP 工具生态**: 4 个独立 MCP 服务器，动态加载工具

4. **Langfuse 可观测性**: 集成 LLM tracing，支持 prompt 和 completion token 统计

5. **异步优先**: PostgreSQL asyncpg 连接池，async/await 贯穿全栈

### 性能洞察

6. **10 线程并行 Embedding**: `ThreadPoolExecutor(max_workers=10)`

7. **查询缓存二级**: Redis (持久化) + Memory (降级)

8. **批量消息保存**: 后台 1 秒批处理，平衡性能和数据一致性

9. **WebSocket 心跳**: 30 秒间隔，90 秒超时，检测断连

10. **Milvus 动态度量检测**: 运行时检测 IP/L2，自动适配搜索参数

### 数据治理洞察

11. **source_mapping.json**: 追踪文件路径和 task_id，支持按源删除

12. **软删除**: 删除源时，从 Milvus 删除向量但保留原始文件

13. **JSONB 消息存储**: 支持复杂的消息结构和 tool_calls

14. **图像 1 小时 TTL**: 临时存储，自动过期清理

### 安全洞察

15. **JWT 认证**: Supabase 兼容，可选启用

16. **WebSocket 认证**: token 参数传递，连接时验证

17. **统一错误响应**: RFC 7807 格式，结构化错误信息

---

## 五、实际数据解读

### 当前知识库状态

| 指标 | 值 | 数据来源 |
|------|-----|----------|
| 文档总数 | 38 | config.json |
| 向量总数 | 动态查询 | /rag/llamaindex/stats |
| 选中源 | 38 (全部) | config.json selected_sources |
| Embedding 维度 | 2560 | Qwen3-Embedding 实测 |
| 分块大小 | 512 | vector_store.py |
| 分块重叠 | 128 | vector_store.py |

### 知识源分布

从文档名分析为 **中国企业出海新加坡合规知识库**:
- 📋 公司注册: ACRA 指南
- 💰 税务: IRAS 所得税、转让定价
- 👷 用工: MOM EP、COMPASS、雇佣法
- 🔒 数据合规: PDPA
- 🏦 金融: 银行指南
- 🌍 投资: FDI、房地产

---

## 六、API 端点速查

### 核心 RAG 接口

| 接口 | 方法 | 功能 | 代码位置 |
|------|------|------|----------|
| `/rag/llamaindex/query` | POST | 增强 RAG 查询 | main.py:1751 |
| `/rag/llamaindex/stats` | GET | RAG 统计 | main.py:1780 |
| `/rag/llamaindex/config` | GET | RAG 配置 | main.py:1724 |
| `/rag/llamaindex/cache/clear` | POST | 清除缓存 | main.py:1803 |
| `/rag/llamaindex/cache/stats` | GET | 缓存统计 | main.py:1821 |
| `/knowledge/status` | GET | 知识库健康 | main.py:1078 |
| `/knowledge/sync` | POST | 同步知识库 | main.py:1175 |
| `/sources/vector-counts` | GET | 向量计数 | main.py:858 |

### WebSocket 接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/ws/chat/{chat_id}` | WebSocket | 实时对话 |

### RESTful v1 接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/api/v1/rag/query` | POST | RAG 查询 |
| `/api/v1/chats` | GET/POST | 会话管理 |
| `/api/v1/sources` | GET | 源列表 |
| `/api/v1/selected-sources` | GET/POST | 选中源管理 |

### 管理员接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/admin/rag/stats` | GET | RAG 统计 |
| `/admin/rag/sources` | GET | 源详情 |
| `/admin/rag/sources/select` | POST | 选择源 |
| `/admin/conversations` | GET | 所有会话 |

---

## 七、关键代码位置索引

### 向量存储
- `vector_store.py:36-124` - CustomEmbeddings (10 并发)
- `vector_store.py:171-174` - RecursiveCharacterTextSplitter
- `vector_store.py:226-266` - Milvus 初始化
- `vector_store.py:268-388` - 文档加载
- `vector_store.py:390-414` - 文档索引
- `vector_store.py:416-461` - 文档检索

### RAG 引擎
- `enhanced_rag.py:41-74` - Qwen3Embedding 封装
- `enhanced_rag.py:126-267` - RedisQueryCache
- `enhanced_rag.py:314-423` - BM25Indexer
- `enhanced_rag.py:436-570` - Reranker
- `enhanced_rag.py:583-656` - HyDEQueryExpander
- `enhanced_rag.py:706-779` - hybrid_search
- `enhanced_rag.py:878-973` - enhanced_rag_query

### Agent
- `agent.py:51-109` - ChatAgent 初始化
- `agent.py:113-135` - MCP 工具初始化
- `agent.py:175-227` - tool_node
- `agent.py:229-290` - generate
- `agent.py:388-445` - _build_graph (LangGraph)
- `agent.py:505-620` - query 主入口

### API
- `main.py:72-99` - 应用生命周期
- `main.py:147-228` - /health
- `main.py:685-757` - WebSocket
- `main.py:779-829` - /ingest
- `main.py:1078-1173` - /knowledge/status

---

## 八、配置与环境变量

### 必需环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MODELS` | - | 可用模型列表 (逗号分隔) |
| `POSTGRES_HOST` | postgres | PostgreSQL 主机 |
| `POSTGRES_PORT` | 5432 | PostgreSQL 端口 |
| `POSTGRES_DB` | chatbot | 数据库名 |
| `POSTGRES_USER` | chatbot_user | 用户名 |
| `POSTGRES_PASSWORD` | chatbot_password | 密码 |

### 可选环境变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `REDIS_HOST` | localhost | Redis 主机 (缓存) |
| `REDIS_PORT` | 6379 | Redis 端口 |
| `QUERY_CACHE_TTL` | 3600 | 缓存 TTL |
| `SUPABASE_JWT_SECRET` | - | JWT 认证密钥 |
| `LANGFUSE_PUBLIC_KEY` | - | Langfuse 公钥 |
| `LANGFUSE_SECRET_KEY` | - | Langfuse 密钥 |
| `RERANKER_HOST` | - | 外部重排序服务 |
| `UPLOAD_DIR` | uploads | 上传目录 |

---

## 九、架构优化建议

### 短期 (1-2 周)

1. **Semantic Chunking**: 根据文档类型选择分块策略
2. **查询分类**: 简单查询 vs 复杂查询选择不同 RAG 路径
3. **增量索引**: 新文档增量添加，避免全量重建

### 中期 (1 个月)

4. **多 Collection 隔离**: 按知识领域分组
5. **监控面板**: Prometheus + Grafana
6. **查询理解层**: 意图检测 + 实体识别

### 长期 (3 个月)

7. **Agentic RAG**: LLM 自主决定检索时机
8. **多模态 RAG**: 图片、表格理解
9. **知识图谱融合**: KG 增强推理

---

## 十、2026 RAG 最佳实践速查

### 架构原则
```
Query Understanding → Retrieval → Reranking → Generation
     ↓                    ↓            ↓
  意图检测            Hybrid Search  Cross-Encoder
  HyDE                RRF            Learning-to-Rank
```

### Chunking 策略
| 场景 | 策略 | 配置 |
|------|------|------|
| 通用 | Recursive | chunk=512, overlap=128 |
| 技术文档 | Semantic | chunk=400, overlap=100 |
| 代码 | Language-aware | 按函数边界 |

### 评估指标
| 维度 | 目标 |
|------|------|
| Grounding | >90% |
| Retrieval Coverage | >80% |
| Answer Faithfulness | >85% |

---

*此分析基于代码底层实现、2025-2026 最新 RAG 研究及第一性原理思维*
*最后更新: 2026-02-24*
*本轮更新: 原子级代码分析 + 六层架构 + MCP 工具集成*
*参考资料: LangGraph 文档, LlamaIndex 文档, Milvus 文档, RFC 7807*

