

## RAG 功能全面分析报告

### 一、项目架构概述

这个项目是基于 **NVIDIA DGX Spark** 的多智能体聊天机器人系统，核心使用以下技术栈：

| 组件 | 技术 | 用途 |
|------|------|------|
| 向量数据库 | **Milvus** (v2.5.15-20250718-3a3b374f-gpu-arm64) | 存储文档嵌入向量 |
| 嵌入模型 | **Qwen3-Embedding-4B** (Q8_0量化) | 将文本转为向量 (2560维) |
| LLM 模型 | **gpt-oss-120B** (mxfp4量化) | 生成回答 |
| 文档处理 | LangChain + UnstructuredLoader | PDF/文档解析 |
| 协议层 | **MCP (Model Context Protocol)** | 智能体工具调用 |
| 对话存储 | **PostgreSQL** (15-alpine) | 聊天历史持久化 |
| 前端框架 | **Next.js** (App Router) | 用户界面 |

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

使用 **Milvus** 作为向量数据库，集合名称固定为 **"context"**，所有文档存储在同一个集合中，通过 `source` 元数据字段进行过滤：

```python
# vector_store.py 第101-112行
def _initialize_store(self):
    self._store = Milvus(
        embedding_function=self.embeddings,
        collection_name="context",  # 固定集合名称
        connection_args={"uri": self.uri},
        auto_id=True
    )
```

**重要架构说明**：
- 系统使用**单个 "context" collection** 存储所有文档
- 每个文档块包含 `source` 元数据字段用于按知识源过滤
- 检索时通过 Milvus 的 `filter_expr` 参数实现按 source 过滤

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

RAG Agent 使用 **LangGraph** 构建工作流，实现简洁的检索-生成 pipeline：

```python
# rag.py 第193-204行
def _build_graph(self):
    """Build and compile the simplified RAG workflow graph."""
    workflow = StateGraph(RAGState)

    workflow.add_node("retrieve", self.retrieve)
    workflow.add_node("generate", self.generate)

    workflow.set_entry_point("retrieve")
    workflow.add_edge("retrieve", "generate")
    workflow.add_edge("generate", END)

    return workflow.compile()
```

**LangGraph 工作流**：
```
START → retrieve (检索文档) → generate (生成回答) → END
```

Supervisor Agent 使用相同的 LangGraph 架构，但具有更复杂的状态机和工具调用能力。

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

**⚠️ 当前实现的架构限制**：
- 系统使用单个 "context" collection 存储所有文档
- 当前 `/collections/{collection_name}` API 会**删除整个 collection**，这会删除所有知识源的向量
- 这是一个需要修复的架构问题

**当前可用的删除方式**：

```bash
# 注意：这会删除整个 collection（所有知识源），谨慎使用！
curl -X DELETE http://localhost:8000/collections/context
```

**后端实现 (`main.py` 第497-511行)**：
```python
@app.delete("/collections/{collection_name}")
async def delete_collection(collection_name: str):
    success = vector_store.delete_collection(collection_name)
    # 删除整个 Milvus collection
```

**推荐实现方案**：需要添加按 source 删除向量的功能（见下文 7.2 节）

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
  1. retrieve: 从 Milvus 检索相关文档（按 source 过滤）
  2. generate: 用 gpt-oss-120b 生成回答
    ↓
返回结果给 Supervisor Agent
```

**MCP 服务器配置 (`client.py` 第39-60行)**：

系统包含 4 个 MCP 服务器：
| 服务器名称 | 文件 | 功能 |
|-----------|------|------|
| rag-server | `tools/mcp_servers/rag.py` | RAG 文档检索 |
| image-understanding-server | `tools/mcp_servers/image_understanding.py` | 图像理解 |
| code-generation-server | `tools/mcp_servers/code_generation.py` | 代码生成 |
| weather-server | `tools/mcp_servers/weather_test.py` | 天气查询（测试用） |

这些服务器通过 `MultiServerMCPClient` (langchain_mcp_adapters) 统一管理。

---

### 五、关键配置文件

| 文件 | 位置 | 作用 |
|------|------|------|
| `config.json` | `backend/config.json` | 知识源列表、选中源、当前模型 |
| `docker-compose.yml` | `assets/` | 主服务配置 (Milvus, PostgreSQL, Backend, Frontend) |
| `docker-compose-models.yml` | `assets/` | 模型服务配置 (LLM, Embedding, VLM) |
| `next.config.ts` | `frontend/` | Next.js 代理配置，将 /api/* 转发到后端 |

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

#### 7.2 添加知识源删除的 UI（需先修复后端架构）

**⚠️ 重要前置说明**：
当前系统存在架构问题：使用单个 "context" collection 存储所有文档，无法按 source 删除向量。
因此，实现删除功能需要先修复后端架构。

**推荐方案**：修改 `vector_store.py` 添加 `delete_by_source` 方法，然后修改 `main.py` 添加 `/sources/{source_name}` API。

需要修改以下文件来实现完整的删除知识源功能：

##### 7.2.1 后端向量删除支持 (vector_store.py)

在 `vector_store.py` 中添加按 source 删除向量的方法（约第365行后）：

```python
# vector_store.py 添加新方法

def delete_by_source(self, source_name: str) -> bool:
    """Delete vectors from a specific source.

    注意：Milvus 当前版本可能需要先检查集合是否有对应字段

    Args:
        source_name: Name of the source to delete vectors for

    Returns:
        bool: True if successful, False otherwise
    """
    try:
        from pymilvus import connections, Collection

        connections.connect(uri=self.uri)
        collection = Collection(name="context")
        collection.load()

        # 构建过滤表达式 - 删除该 source 的所有向量
        filter_expr = f'source == "{source_name}"'

        # 删除符合条件的向量
        collection.delete(filter_expr)

        # 释放集合
        collection.release()

        logger.debug({
            "message": "Deleted vectors by source",
            "source": source_name
        })

        return True
    except Exception as e:
        logger.error({
            "message": "Error deleting vectors by source",
            "source": source_name,
            "error": str(e)
        })
        return False
```

##### 7.2.2 后端 API (main.py)

在 `main.py` 中添加删除知识源的 API（约第512行后）：

```python
@app.delete("/sources/{source_name}")
async def delete_source(source_name: str):
    """Delete a knowledge source from config and vector store.

    Args:
        source_name: Name of the source to delete
    """
    try:
        # 1. 从 Milvus 中删除该 source 的向量
        vector_store.delete_by_source(source_name)

        # 2. 从 config.json 的 sources 中移除
        config = config_manager.read_config()

        if source_name not in config.sources:
            raise HTTPException(status_code=404, detail=f"Source '{source_name}' not found")

        # 移除 source
        config.sources = [s for s in config.sources if s != source_name]

        # 如果在 selected_sources 中也要移除
        if source_name in config.selected_sources:
            config.selected_sources = [s for s in config.selected_sources if s != source_name]

        config_manager.write_config(config)

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
| 向量存储初始化 | `vector_store.py` | 101-112 | Milvus 连接，固定 collection_name="context" |
| 文档加载 | `vector_store.py` | 114-234 | _load_documents 方法，支持 PDF/TXT/DOCX |
| 文档索引 | `vector_store.py` | 236-260 | index_documents 方法 |
| 向量检索（按source过滤）| `vector_store.py` | 285-323 | get_documents 方法，使用 filter_expr |
| 删除 Collection | `vector_store.py` | 325-365 | delete_collection 方法（删除整个集合）|
| 按 Source 删除向量 | `vector_store.py` | 需新增 | 建议添加 delete_by_source 方法 |
| RAG 检索 | `rag.py` | 117-139 | retrieve 方法 |
| RAG 生成 | `rag.py` | 142-187 | generate 方法 |
| RAG MCP 工具 | `rag.py` | 212-249 | @mcp.tool() search_documents |
| 删除 Collection API | `main.py` | 497-511 | /collections/{collection_name} 端点 |
| 删除 Source API | `main.py` | 需新增 | 建议添加 /sources/{source_name} 端点 |
| 知识源配置读取 | `config.py` | 88-114 | read_config 方法 |
| 知识源配置更新 | `config.py` | 151-154 | updated_selected_sources |
| 聊天历史存储 | `postgres_storage.py` | 全文 | 对话持久化 |
| MCP 客户端配置 | `client.py` | 37-60 | server_configs 定义 |
| Agent 工具初始化 | `agent.py` | 105-144 | init_tools 方法 |
| Agent 工具调用 | `agent.py` | 212-274 | tool_node 方法 |
| Supervisor 系统提示 | `prompts.py` | SUPERVISOR_AGENT_STR | 智能体提示词 |
| 前端 API 代理 | `next.config.ts` | 20-27 | rewrites 配置 /api -> backend:8000 |
| 前端知识源选择 | `Sidebar.tsx` | 279-309 | handleSourceToggle |
| 前端文件上传 | `DocumentIngestion.tsx` | 50-82 | handleIngestSubmit |

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

# 测试获取选中的知识源
curl http://localhost:8000/selected_sources

# 测试文档摄取
curl -X POST http://localhost:8000/ingest \
  -F "files=@test.pdf"

# 检查摄取状态
curl http://localhost:8000/ingest/status/{task_id}

# ⚠️ 删除 Collection（会删除所有知识源，谨慎使用！）
curl -X DELETE http://localhost:8000/collections/context

# 获取可用模型
curl http://localhost:8000/available_models

# 获取聊天列表
curl http://localhost:8000/chats
```

---

### 十、常见问题排查

| 问题 | 原因 | 解决方案 |
|------|------|----------|
| 上传文档后搜索不到 | 文档未完成索引或 source 未在 selected_sources 中 | 检查 `/ingest/status/{task_id}`，确认已选择知识源 |
| 检索结果不准确 | chunk_size 不合适或 selected_sources 为空 | 调整大小或 overlap，确保已勾选知识源 |
| 模型响应很慢 | 内存不足或模型未加载 | 检查 `nvidia-smi` 内存使用，等待模型加载完成 |
| Milvus 连接失败 | 服务未启动或网络问题 | `docker ps` 检查 milvus-standalone 容器状态 |
| 前端无法连接后端 | Next.js 代理未配置或后端未启动 | 检查 `next.config.ts` rewrites 配置 |
| MCP 工具不可用 | MCP 服务器未就绪 | 查看后端日志，确认 agent 初始化完成 |
| 删除知识源后仍可搜索 | 当前实现只删除 config，未删除向量 | 需要实现 delete_by_source 方法 |

---

需要我帮你实现某个具体功能吗？