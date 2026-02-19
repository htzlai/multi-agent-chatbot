

## RAG 功能全面分析报告

### 一、项目架构概述

这个项目是基于 **NVIDIA DGX Spark** 的多智能体聊天机器人系统，核心使用以下技术栈：

| 组件 | 技术 | 用途 |
|------|------|------|
| 向量数据库 | **Milvus** (v2.5.15) | 存储文档嵌入向量 |
| 嵌入模型 | **Qwen3-Embedding-4B** | 将文本转为向量 |
| LLM 模型 | **gpt-oss-120B** | 生成回答 |
| 文档处理 | LangChain + UnstructuredLoader | PDF/文档解析 |
| 协议层 | **MCP (Model Context Protocol)** | 智能体工具调用 |
| 对话存储 | PostgreSQL | 聊天历史持久化 |

---

### 二、RAG 实现原理

#### 1. 文档摄取流程 (Ingestion Pipeline)

```
用户上传文件 → 后端 /ingest API → 文本提取 → 分块 → 嵌入 → 向量存储
```

关键代码在 `vector_store.py` 和 `utils.py` 中：

```python
# 文本分块配置 (vector_store.py 第86-89行)
self.text_splitter = RecursiveCharacterTextSplitter(
    chunk_size=1000,
    chunk_overlap=200
)
```

**支持的文档格式**：
- PDF（使用 UnstructuredLoader 或 PyPDF fallback）
- Word (.docx)
- 纯文本文件

#### 2. 向量存储 (Vector Store)

使用 **Milvus** 作为向量数据库，嵌入向量维度为 **2560**：

```python
# vector_store.py 第102-107行
self._store = Milvus(
    embedding_function=self.embeddings,
    collection_name="context",
    connection_args={"uri": self.uri},
    auto_id=True
)
```

#### 3. 检索流程 (Retrieval)

当用户提问时，RAG MCP 服务器执行以下步骤：

```python
# rag.py 第117-139行
def retrieve(self, state: RAGState) -> Dict:
    # 1. 获取选中的源
    sources = state.get("sources", [])
    
    # 2. 向量相似度搜索（默认 k=8）
    retrieved_docs = self.vector_store.get_documents(
        state["question"], 
        sources=sources
    )
    
    # 3. 返回相关文档
    return {"context": retrieved_docs}
```

#### 4. 生成回答 (Generation)

```python
# rag.py 第142-187行
async def generate(self, state: RAGState) -> Dict:
    # 1. 将检索到的文档内容拼接
    docs_content = self._hydrate_context(context)
    
    # 2. 构建提示词
    system_prompt = self.generation_prompt.format(context=docs_content)
    
    # 3. 调用 LLM 生成回答
    response = await self.model_client.chat.completions.create(
        model=self.model_name,
        messages=[{"role": "system", "content": system_prompt},
                  {"role": "user", "content": state["question"]}]
    )
```

---

### 三、知识库管理操作

#### 1. 增加文档 (Add Documents)

**方式一：前端界面上传**
- 访问 `http://localhost:3000`
- 点击左侧边栏的 **"Upload Documents"** 按钮
- 选择文件（支持多选）
- 点击 **"Ingest Documents"**

**方式二：API 直接调用**

```bash
curl -X POST http://localhost:8000/ingest \
  -F "files=@your_document.pdf"
```

后端会自动：
1. 保存文件到 `backend/uploads/{task_id}/` 目录
2. 提取文本内容
3. 分块并生成嵌入向量
4. 存储到 Milvus
5. 更新 `config.json` 中的 `sources` 列表

#### 2. 查看可用知识源

```bash
# 获取所有已摄入的文档
curl http://localhost:8000/sources

# 获取当前选中的知识源
curl http://localhost:8000/selected_sources
```

返回格式：
```json
{
  "sources": [
    "文档1.pdf",
    "文档2.docx"
  ]
}
```

#### 3. 选择/切换知识源

在 `config.json` 中配置 `selected_sources`：

```json
{
  "sources": ["文档1.pdf", "文档2.pdf", "文档3.docx"],
  "selected_sources": ["文档1.pdf", "文档2.pdf"]
}
```

前端界面支持勾选复选框实时切换：

```typescript
// Sidebar.tsx 第279-309行
const handleSourceToggle = async (source: string) => {
  // 切换选中状态后调用 API
  await fetch("/api/selected_sources", {
    method: "POST",
    body: JSON.stringify(newSelectedSources)
  });
};
```

#### 4. 删除知识源

**方式一：删除整个 Collection**

```bash
curl -X DELETE http://localhost:8000/collections/文档名
```

后端实现 (`main.py` 第497-511行)：
```python
@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    success = vector_store.delete_collection(collection_name)
    # 同时会触发 config.json 中 sources 的更新
```

**方式二：手动删除文件**
- 删除 `backend/uploads/` 目录下的文件
- 手动编辑 `config.json` 移除对应条目

---

### 四、模型调用详解

#### 1. 模型服务架构

```
┌─────────────────────────────────────────────────────────────┐
│                     Docker Compose                          │
├─────────────────────────────────────────────────────────────┤
│  gpt-oss-120b (llama.cpp server)  :8000                   │
│  qwen3-embedding (llama.cpp)       :8000                   │
│  qwen2.5-vl (TensorRT)             :8000                   │
│  milvus                            :19530                  │
│  postgres                          :5432                    │
└─────────────────────────────────────────────────────────────┘
```

#### 2. 模型配置 (`docker-compose-models.yml`)

**主模型 (Supervisor Agent)**
```yaml
gpt-oss-120b:
  command:
    - "-m"
    - "/models/gpt-oss-120b-mxfp4-00001-of-00003.gguf"
    - "--port"
    - "8000"
    - "--ctx-size"
    - "16384"
```

**嵌入模型**
```yaml
qwen3-embedding:
  command:
    - "-m"
    - "/models/Qwen3-Embedding-4B-Q8_0.gguf"
    - "--port"
    - "8000"
    - "--embeddings"    # 启用嵌入 API
```

#### 3. 客户端调用 (agent.py)

```python
# 第161-164行
self.model_client = AsyncOpenAI(
    base_url=f"http://{self.current_model}:8000/v1",
    api_key="api_key"
)

# 第315-322行
stream = await self.model_client.chat.completions.create(
    model=self.current_model,
    messages=messages,
    temperature=0,
    stream=True,
    **tool_params  # 工具调用参数
)
```

#### 4. MCP 工具调用流程

```
用户问题 → Supervisor Agent (gpt-oss-120b)
    ↓
判断需要 RAG → 调用 search_documents 工具
    ↓
RAG MCP Server:
  1. retrieve: 从 Milvus 检索相关文档
  2. generate: 用 gpt-oss-120b 生成回答
    ↓
返回结果给 Supervisor Agent
```

---

### 纯检索测试 (RAG Debug)

除了完整的 RAG 问答流程，系统还提供了**纯检索测试端点**，用于调试和评估 RAG 检索效果。

#### 纯检索 vs RAG 问答

| 特性 | 纯检索 `/rag/retrieve` | RAG 问答 WebSocket |
|------|------------------------|-------------------|
| 调用 GPU | ❌ 否 | ✅ 是 |
| 调用 LLM | ❌ 否 | ✅ gpt-oss-120b |
| 用途 | 调试检索效果 | 完整对话 |
| 响应速度 | 快 | 较慢 |

#### API 端点

```
POST /rag/retrieve
```

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|---------|------|
| `query` | string | ✅ | - | 检索查询 |
| `sources` | string[] | ❌ | null | 文档源过滤 |
| `k` | int | ❌ | 8 | 返回结果数量 |

#### 使用示例

```bash
# 检索所有文档
curl -X POST http://localhost:8000/rag/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是 Geotab", "k": 3}'

# 指定文档源
curl -X POST http://localhost:8000/rag/retrieve \
  -H "Content-Type: application/json" \
  -d '{"query": "什么是人工智能", "k": 2, "sources": ["文档名.pdf"]}'
```

#### 返回格式

```json
{
  "status": "success",
  "query": "什么是 Geotab",
  "documents": [
    {
      "source": "硬件档案：Geotab GO 系列.docx",
      "content": "检索到的文本内容...",
      "score": 0.85
    }
  ],
  "count": 3
}
```

#### 适用场景

1. **调试检索效果** - 查看特定查询检索到了哪些文档
2. **优化 chunk size** - 评估不同分块策略的效果
3. **排查质量问题** - 检查是否检索到相关文档
4. **评估 sources 配置** - 验证选中的文档源是否正确

---

### 五、关键配置文件

| 文件 | 位置 | 作用 |
|------|------|------|
| `config.json` | `backend/config.json` | 知识源列表、选中源、当前模型 |
| `docker-compose.yml` | `assets/` | 主服务配置 (Milvus, PostgreSQL, Backend, Frontend) |
| `docker-compose-models.yml` | `assets/` | 模型服务配置 |

---

### 六、扩展建议

如果你想扩展 RAG 功能，可以考虑：

1. **添加更多文档格式支持**
   - 在 `vector_store.py` 的 `_load_documents` 方法中添加更多 loader

2. **优化检索效果**
   - 调整 `chunk_size` 和 `chunk_overlap`
   - 使用混合搜索 (Milvus 支持全文 + 向量搜索)

3. **添加知识源删除的 UI**
   - 当前前端没有直接删除知识源的按钮

4. **批量管理**
   - 添加 `/sources/batch-delete` 等 API

---

### 七、扩展功能实现指南

#### 7.1 添加更多文档格式支持

在 `vector_store.py` 的 `_load_documents` 方法中添加更多文档格式的 loader：

```python
# vector_store.py 文件头部导入
from langchain_community.document_loaders import (
    UnstructuredLoader,
    PyPDFLoader,
    TextLoader,
    Docx2txtLoader,
    CSVLoader,
    HTMLLoader,
    MarkdownLoader,
)

# _load_documents 方法中添加 (约第131-145行)
def _load_documents(self, file_paths: List[str] = None, input_dir: str = None) -> List[str]:
    # ... 现有代码 ...

    for file_path in file_paths:
        file_ext = os.path.splitext(file_path)[1].lower()

        # 根据文件类型选择合适的 loader
        if file_ext == ".pdf":
            loader = PyPDFLoader(file_path)  # 或继续使用 UnstructuredLoader
        elif file_ext == ".docx":
            loader = Docx2txtLoader(file_path)
        elif file_ext == ".txt":
            loader = TextLoader(file_path, encoding="utf-8")
        elif file_ext == ".csv":
            loader = CSVLoader(file_path)
        elif file_ext == ".html":
            loader = HTMLLoader(file_path)
        elif file_ext == ".md":
            loader = MarkdownLoader(file_path)
        else:
            loader = UnstructuredLoader(file_path)

        docs = loader.load()
```

#### 7.2 添加知识源删除的 UI

需要修改以下文件来实现删除知识源功能：

##### 7.2.1 后端 API (main.py)

在 `main.py` 中添加删除知识源的 API（约第512行后）：

```python
@app.delete("/sources/{source_name}")
async def delete_source(source_name: str):
    """Delete a knowledge source from config and optionally from vector store.

    Args:
        source_name: Name of the source to delete
    """
    try:
        # 1. 从 config.json 的 sources 中移除
        config = config_manager.read_config()

        if source_name not in config.sources:
            raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")

        # 移除 source
        config.sources = [s for s in config.sources if s != source_name]

        # 如果在 selected_sources 中也要移除
        if source_name in config.selected_sources:
            config.selected_sources = [s for s in config.selected_sources if s != source_name]

        config_manager.write_config(config)

        # 2. 可选：从 Milvus 中删除该 source 的向量
        # 注意：这需要修改 vector_store.py 支持按 source 删除

        return {
            "status": "success",
            "message": f"Source '{source_name}' deleted successfully",
            "remaining_sources": config.sources
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error deleting source: {str(e)}")
```

##### 7.2.2 后端向量删除支持 (vector_store.py)

在 `vector_store.py` 中添加按 source 删除向量的方法（约第365行后）：

```python
def delete_by_source(self, source_name: str) -> bool:
    """Delete vectors from a specific source.

    Args:
        source_name: Name of the source to delete vectors for

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from pymilvus import connections, Collection

        connections.connect(uri=self.uri)
        collection = Collection(name="context")

        # 构建过滤表达式
        filter_expr = f'source == "{source_name}"'

        # 删除符合条件的向量
        # 注意：这需要 Milvus 集合有 source 字段
        # 如果没有，需要先添加字段或使用其他方式

        logger.debug({
            "message": "Deleting vectors by source",
            "source": source_name,
            "filter": filter_expr
        })

        # 方法1：如果有 source 字段
        # collection.delete(filter_expr)

        # 方法2：重新索引（删除整个 collection 后重新添加其他文档）
        # 这比较复杂，建议使用软删除（标记为 deleted）

        return True
    except Exception as e:
        logger.error({
            "message": "Error deleting vectors by source",
            "source": source_name,
            "error": str(e)
        })
        return False
```

##### 7.2.3 前端组件 (Sidebar.tsx)

在 `Sidebar.tsx` 中添加删除按钮（约第570-581行）：

```typescript
// 添加删除知识源的处理函数
const handleDeleteSource = async (source: string, e: React.MouseEvent) => {
  e.stopPropagation(); // 防止触发复选框切换

  const confirmDelete = window.confirm(
    `Are you sure you want to delete "${source}"? This will remove it from the knowledge base.`
  );

  if (!confirmDelete) return;

  try {
    const response = await fetch(`/api/sources/${encodeURIComponent(source)}`, {
      method: "DELETE"
    });

    if (!response.ok) {
      console.error("Failed to delete source");
      alert("Failed to delete source. Please try again.");
      return;
    }

    // 从本地状态中移除
    setAvailableSources(prev => prev.filter(s => s !== source));
    setSelectedSources(prev => prev.filter(s => s !== source));

    // 刷新知识源列表
    fetchSources();

    console.log(`Successfully deleted source: ${source}`);
  } catch (error) {
    console.error("Error deleting source:", error);
    alert("An error occurred while deleting the source.");
  }
};
```

修改知识源显示部分（约第570-582行），添加删除按钮：

```typescript
availableSources.map(source => (
  <div key={source} className={styles.sourceItem}>
    <input
      type="checkbox"
      id={`source-${source}`}
      checked={selectedSources.includes(source)}
      onChange={() => handleSourceToggle(source)}
    />
    <label htmlFor={`source-${source}`} className={styles.sourceLabel}>
      {source}
    </label>
    <button
      className={styles.deleteSourceButton}
      onClick={(e) => handleDeleteSource(source, e)}
      title="Delete source"
    >
      ×
    </button>
  </div>
))
```

##### 7.2.4 前端样式 (Sidebar.module.css)

添加删除按钮的样式：

```css
/* Sidebar.module.css 中添加 */
.sourceItem {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.sourceLabel {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}

.deleteSourceButton {
  background: none;
  border: none;
  color: #999;
  cursor: pointer;
  font-size: 18px;
  padding: 2px 6px;
  border-radius: 4px;
  transition: all 0.2s ease;
}

.deleteSourceButton:hover {
  background-color: #fee2e2;
  color: #dc2626;
}
```

#### 7.3 批量管理 API

添加批量删除和批量操作的 API：

```python
# main.py 中添加

@app.post("/sources/batch-delete")
async def batch_delete_sources(sources: List[str]):
    """Batch delete knowledge sources.

    Args:
        sources: List of source names to delete
    """
    try:
        config = config_manager.read_config()
        deleted = []
        failed = []

        for source in sources:
            if source in config.sources:
                config.sources = [s for s in config.sources if s != source]
                if source in config.selected_sources:
                    config.selected_sources = [s for s in config.selected_sources if s != source]
                deleted.append(source)
            else:
                failed.append(source)

        config_manager.write_config(config)

        return {
            "status": "success",
            "deleted": deleted,
            "failed": failed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error batch deleting sources: {str(e)}")

@app.post("/sources/batch-select")
async def batch_select_sources(sources: List[str]):
    """Batch select knowledge sources.

    Args:
        sources: List of source names to select
    """
    try:
        config = config_manager.read_config()

        # 验证所有 source 都存在
        valid_sources = [s for s in sources if s in config.sources]

        config.selected_sources = valid_sources
        config_manager.write_config(config)

        return {
            "status": "success",
            "selected_sources": valid_sources
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error batch selecting sources: {str(e)}")
```

---

### 八、关键代码位置索引

| 功能 | 文件 | 行号 | 描述 |
|------|------|------|------|
| 文本分块配置 | `vector_store.py` | 86-89 | RecursiveCharacterTextSplitter |
| 向量存储初始化 | `vector_store.py` | 101-112 | Milvus 连接 |
| 文档加载 | `vector_store.py` | 114-234 | _load_documents 方法 |
| 文档索引 | `vector_store.py` | 236-260 | index_documents 方法 |
| 向量检索 | `vector_store.py` | 285-323 | get_documents 方法 |
| 删除 Collection | `vector_store.py` | 325-365 | delete_collection 方法 |
| RAG 检索 | `rag.py` | 117-139 | retrieve 方法 |
| RAG 生成 | `rag.py` | 142-187 | generate 方法 |
| 知识源删除 API | `main.py` | 497-511 | delete_collection 端点 |
| 知识源配置读取 | `config.py` | 88-114 | read_config 方法 |
| 知识源配置更新 | `config.py` | 151-154 | updated_selected_sources |
| 聊天历史存储 | `postgres_storage.py` | 全文 | 对话持久化 |
| 前端知识源选择 | `Sidebar.tsx` | 279-309 | handleSourceToggle |
| 前端文件上传 | `DocumentIngestion.tsx` | 全文 | 文档摄取 UI |
| MCP 工具注册 | `rag.py` | 212-249 | @mcp.tool() 装饰器 |
| Agent 工具调用 | `agent.py` | 212-274 | tool_node 方法 |

---

### 九、调试技巧

#### 9.1 查看 Milvus 中的数据

```python
# 连接到 Milvus 并查询
from pymilvus import connections, Collection, utility

connections.connect(uri="http://localhost:19530")

# 列出所有集合
print(utility.list_collections())

# 查看集合中的数据
collection = Collection("context")
collection.load()
results = collection.query(expr="id > 0", output_fields=["source", "text"])
print(results)
```

#### 9.2 查看日志

```bash
# 查看后端日志
docker logs backend

# 查看 Milvus 日志
docker logs milvus-standalone

# 实时查看所有服务日志
docker compose -f docker-compose.yml -f docker-compose-models.yml logs -f
```

#### 9.3 API 测试

```bash
# 测试知识源列表
curl http://localhost:8000/sources

# 测试选择知识源
curl -X POST http://localhost:8000/selected_sources \
  -H "Content-Type: application/json" \
  -d '["文档1.pdf"]'

# 测试删除知识源
curl -X DELETE http://localhost:8000/sources/文档1.pdf

# 测试文档摄取
curl -X POST http://localhost:8000/ingest \
  -F "files=@test.pdf"
```

---

### 十、常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 上传文档后搜索不到 | 文档未完成索引 | 检查 `/ingest/status/{task_id}` |
| 检索结果不准确 | chunk_size 不合适 | 调整大小或 overlap |
| 模型响应很慢 | 内存不足 | 检查 `nvidia-smi` 内存使用 |
| Milvus 连接失败 | 服务未启动 | `docker ps` 检查 milvus 容器 |
| 前端无法连接后端 | CORS 配置 | 检查 main.py 中的 CORS 配置 |

---

### 十一、前端与后端完整接口文档

#### 11.1 前端代理配置

前端通过 Next.js 的 `next.config.ts` 配置 API 代理：

```typescript
// frontend/next.config.ts 第20-27行
async rewrites() {
  return [
    {
      source: '/api/:path*',
      destination: 'http://backend:8000/:path*',
    },
  ];
}
```

前端请求 `/api/xxx` 会被代理到后端 `http://backend:8000/xxx`。

#### 11.2 后端 API 端点总览

| 序号 | 方法 | 端点 | 功能 | 所在文件 |
|------|------|------|------|----------|
| 1 | WebSocket | `/ws/chat/{chat_id}` | 实时聊天 | main.py:114 |
| 2 | POST | `/upload-image` | 上传图片 | main.py:159 |
| 3 | POST | `/ingest` | 文档摄取 | main.py:178 |
| 4 | GET | `/ingest/status/{task_id}` | 摄取状态 | main.py:231 |
| 5 | GET | `/sources` | 获取知识源列表 | main.py:247 |
| 6 | GET | `/selected_sources` | 获取选中的知识源 | main.py:257 |
| 7 | POST | `/selected_sources` | 更新选中的知识源 | main.py:267 |
| 8 | GET | `/selected_model` | 获取当前模型 | main.py:281 |
| 9 | POST | `/selected_model` | 更新当前模型 | main.py:291 |
| 10 | GET | `/available_models` | 获取可用模型列表 | main.py:306 |
| 11 | GET | `/chats` | 获取所有会话 | main.py:316 |
| 12 | GET | `/chat_id` | 获取当前会话ID | main.py:326 |
| 13 | POST | `/chat_id` | 更新当前会话ID | main.py:357 |
| 14 | GET | `/chat/{chat_id}/metadata` | 获取会话元数据 | main.py:378 |
| 15 | POST | `/chat/rename` | 重命名会话 | main.py:398 |
| 16 | POST | `/chat/new` | 创建新会话 | main.py:418 |
| 17 | DELETE | `/chat/{chat_id}` | 删除会话 | main.py:440 |
| 18 | DELETE | `/chats/clear` | 清除所有会话 | main.py:467 |
| 19 | DELETE | `/collections/{collection_name}` | 删除向量集合 | main.py:497 |
| 20 | POST | `/rag/retrieve` | 纯检索测试 | main.py:281 |

#### 11.3 详细接口规范

---

##### 1. WebSocket 实时聊天

**端点**: `WS /ws/chat/{chat_id}`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:114-157` |
| 前端位置 | `QuerySection.tsx:237` |

**连接示例**:
```typescript
const ws = new WebSocket(`ws://localhost:8000/ws/chat/${chatId}`);
```

**发送消息格式**:
```json
{
  "message": "用户问题",
  "image_id": "可选图片ID"
}
```

**接收消息类型**:

| type | 说明 | 数据结构 |
|------|------|----------|
| `history` | 聊天历史 | `{ messages: [...] }` |
| `token` | AI 回复流 | `{ token: "文本片段" }` |
| `tool_token` | 工具输出流 | `{ token: "工具输出" }` |
| `tool_start` | 工具开始 | `{ data: "工具名称" }` |
| `tool_end` | 工具结束 | `{ data: "工具名称" }` |
| `node_start` | 节点开始 | `{ data: "节点名称" }` |
| `node_end` | 节点结束 | `{ data: "节点名称" }` |
| `error` | 错误信息 | `{ content: "错误消息" }` |

**前端处理代码** (`QuerySection.tsx:245-303`):
```typescript
ws.onmessage = (event) => {
  const msg = JSON.parse(event.data);
  const type = msg.type;
  const text = msg.data ?? msg.token ?? "";

  switch (type) {
    case "history":
      setResponse(JSON.stringify(msg.messages));
      break;
    case "token":
      setResponse(prev => prev + text);
      break;
    case "tool_token":
      setToolOutput(prev => prev + text);
      break;
    case "tool_start":
      setGraphStatus(`calling tool: ${msg.data}`);
      break;
    case "tool_end":
    case "node_end":
      setGraphStatus("");
      break;
  }
};
```

---

##### 2. 上传图片

**端点**: `POST /upload-image`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:159-176` |
| 请求格式 | `multipart/form-data` |

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `image` | File | 是 | 图片文件 |
| `chat_id` | string | 是 | 关联的会话ID |

**返回格式**:
```json
{
  "image_id": "生成的UUID"
}
```

---

##### 3. 文档摄取

**端点**: `POST /ingest`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:178-228` |
| 请求格式 | `multipart/form-data` |

**请求参数**:

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `files` | File[] | 是 | 要摄取的文件（支持多个） |

**返回格式**:
```json
{
  "message": "Files queued for processing. Indexing X files in the background.",
  "files": ["file1.pdf", "file2.docx"],
  "status": "queued",
  "task_id": "uuid字符串"
}
```

**前端调用** (`DocumentIngestion.tsx:62-65`):
```typescript
const formData = new FormData();
for (let i = 0; i < files.length; i++) {
  formData.append("files", files[i]);
}
const res = await fetch("/api/ingest", {
  method: "POST",
  body: formData,
});
```

---

##### 4. 摄取状态查询

**端点**: `GET /ingest/status/{task_id}`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:231-244` |

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `task_id` | string | 摄取任务的UUID |

**返回格式**:
```json
{
  "status": "completed"  // queued | saving_files | loading_documents | indexing_documents | completed | failed
}
```

---

##### 5. 获取知识源列表

**端点**: `GET /sources`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:247-254` |

**返回格式**:
```json
{
  "sources": [
    "文档1.pdf",
    "文档2.docx"
  ]
}
```

**前端调用** (`Sidebar.tsx:133`):
```typescript
const response = await fetch("/api/sources");
const data = await response.json();
setAvailableSources(data.sources || []);
```

---

##### 6. 获取选中的知识源

**端点**: `GET /selected_sources`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:257-264` |

**返回格式**:
```json
{
  "sources": ["文档1.pdf"]
}
```

---

##### 7. 更新选中的知识源

**端点**: `POST /selected_sources`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:267-278` |

**请求体**:
```json
["文档1.pdf", "文档2.pdf"]
```

**返回格式**:
```json
{
  "status": "success",
  "message": "Selected sources updated successfully"
}
```

**前端调用** (`Sidebar.tsx:293-297`):
```typescript
await fetch("/api/selected_sources", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(newSelectedSources)
});
```

---

##### 8. 获取当前模型

**端点**: `GET /selected_model`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:281-288` |

**返回格式**:
```json
{
  "model": "gpt-oss-120b"
}
```

**前端调用** (`Sidebar.tsx:69`):
```typescript
const modelResponse = await fetch("/api/selected_model");
const { model } = await modelResponse.json();
setSelectedModel(model);
```

---

##### 9. 更新当前模型

**端点**: `POST /selected_model`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:291-303` |

**请求体** (`models.py:34-35`):
```json
{
  "model": "gpt-oss-120b"
}
```

**返回格式**:
```json
{
  "status": "success",
  "message": "Selected model updated successfully"
}
```

**前端调用** (`Sidebar.tsx:477-481`):
```typescript
await fetch("/api/selected_model", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify({ model: newModel })
});
```

---

##### 10. 获取可用模型列表

**端点**: `GET /available_models`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:306-313` |

**返回格式**:
```json
{
  "models": ["gpt-oss-120b", "gpt-oss-20b"]
}
```

**前端调用** (`Sidebar.tsx:107`):
```typescript
const response = await fetch("/api/available_models");
const data = await response.json();
const models = data.models.map((modelId: string) => ({
  id: modelId,
  name: modelId.split('-').map(word => word.charAt(0).toUpperCase() + word.slice(1)).join(' ')
}));
```

---

##### 11. 获取所有会话列表

**端点**: `GET /chats`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:316-323` |

**返回格式**:
```json
{
  "chats": ["uuid1", "uuid2", "uuid3"]
}
```

---

##### 12. 获取当前会话ID

**端点**: `GET /chat_id`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:326-354` |

**返回格式**:
```json
{
  "status": "success",
  "chat_id": "uuid字符串"
}
```

**说明**: 如果当前没有会话，会自动创建一个新会话。

---

##### 13. 更新当前会话ID

**端点**: `POST /chat_id`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:357-375` |

**请求体** (`models.py:27-28`):
```json
{
  "chat_id": "uuid字符串"
}
```

---

##### 14. 获取会话元数据

**端点**: `GET /chat/{chat_id}/metadata`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:378-395` |

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `chat_id` | string | 会话UUID |

**返回格式**:
```json
{
  "name": "Chat 12345678"
}
```

---

##### 15. 重命名会话

**端点**: `POST /chat/rename`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:398-415` |

**请求体** (`models.py:30-32`):
```json
{
  "chat_id": "uuid字符串",
  "new_name": "新名称"
}
```

**返回格式**:
```json
{
  "status": "success",
  "message": "Chat xxx renamed to 新名称"
}
```

---

##### 16. 创建新会话

**端点**: `POST /chat/new`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:418-437` |

**返回格式**:
```json
{
  "status": "success",
  "message": "New chat created",
  "chat_id": "新会话UUID"
}
```

---

##### 17. 删除会话

**端点**: `DELETE /chat/{chat_id}`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:440-464` |

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `chat_id` | string | 要删除的会话UUID |

**返回格式**:
```json
{
  "status": "success",
  "message": "Chat xxx deleted successfully"
}
```

---

##### 18. 清除所有会话

**端点**: `DELETE /chats/clear`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:467-494` |

**返回格式**:
```json
{
  "status": "success",
  "message": "Cleared X chats and created new chat",
  "new_chat_id": "新会话UUID",
  "cleared_count": X
}
```

---

##### 19. 删除向量集合

**端点**: `DELETE /collections/{collection_name}`

| 项目 | 说明 |
|------|------|
| 文件位置 | `main.py:497-511` |

**路径参数**:

| 参数 | 类型 | 说明 |
|------|------|------|
| `collection_name` | string | 要删除的集合名称 |

**返回格式**:
```json
{
  "status": "success",
  "message": "Collection 'xxx' deleted successfully"
}
```

---

#### 11.4 MCP 工具列表

系统通过 MCP 协议暴露以下工具给 LLM：

| 工具名称 | 所在文件 | 功能描述 |
|----------|----------|----------|
| `search_documents` | `rag.py:212-249` | RAG 文档搜索 |
| `explain_image` | `image_understanding.py:64-68` | 图片理解 |
| `write_code` | `code_generation.py:31-36` | 代码生成 |
| `get_weather` | `weather_test.py:52-60` | 获取天气 |
| `get_rain_forecast` | `weather_test.py:61-68` | 获取降雨预报 |

**search_documents 详细参数**:
```python
# rag.py:213-222
@mcp.tool()
async def search_documents(query: str) -> str:
    """Search documents uploaded by the user to generate fast, grounded answers.

    Performs a simple RAG pipeline that retrieves relevant documents and generates answers.

    Args:
        query: The question or query to search for.

    Returns:
        A concise answer based on the retrieved documents.
    """
```

---

#### 11.5 PostgreSQL 存储接口 (内部)

| 方法 | 函数名 | 行号 | 功能 |
|------|--------|------|------|
| async | `init_pool` | postgres_storage.py:89 | 初始化连接池 |
| async | `get_messages` | postgres_storage.py:289 | 获取消息 |
| async | `save_messages` | postgres_storage.py:314 | 保存消息（批量） |
| async | `save_messages_immediate` | postgres_storage.py:321 | 立即保存消息 |
| async | `add_message` | postgres_storage.py:378 | 添加单条消息 |
| async | `delete_conversation` | postgres_storage.py:385 | 删除会话 |
| async | `list_conversations` | postgres_storage.py:402 | 列出所有会话 |
| async | `store_image` | postgres_storage.py:425 | 存储图片 |
| async | `get_image` | postgres_storage.py:445 | 获取图片 |
| async | `get_chat_metadata` | postgres_storage.py:471 | 获取会话元数据 |
| async | `set_chat_metadata` | postgres_storage.py:502 | 设置会话元数据 |

---

#### 11.6 数据模型定义

**ChatConfig** (`models.py:20-25`):
```python
class ChatConfig(BaseModel):
    sources: List[str]                           # 所有知识源
    models: List[str]                            # 可用模型列表
    selected_model: Optional[str] = None          # 当前选中的模型
    selected_sources: Optional[List[str]] = None  # 当前选中的知识源
    current_chat_id: Optional[str] = None         # 当前会话ID
```

**请求模型**:

```python
# ChatIdRequest (models.py:27-28)
class ChatIdRequest(BaseModel):
    chat_id: str

# ChatRenameRequest (models.py:30-32)
class ChatRenameRequest(BaseModel):
    chat_id: str
    new_name: str

# SelectedModelRequest (models.py:34-35)
class SelectedModelRequest(BaseModel):
    model: str
```

---

#### 11.7 前端组件与 API 对应关系

| 前端组件 | 使用的 API |
|----------|-----------|
| `page.tsx` | `/api/chat_id` (GET/POST) |
| `Sidebar.tsx` | `/api/sources`, `/api/selected_sources`, `/api/selected_model`, `/api/available_models`, `/api/chats`, `/api/chat/{id}/metadata`, `/api/chat/rename`, `/api/chat/new`, `/api/chat/{id}` (DELETE), `/api/chats/clear` |
| `QuerySection.tsx` | `/api/selected_sources`, WebSocket `/ws/chat/{chat_id}` |
| `DocumentIngestion.tsx` | `/api/ingest` |

---
