# RAG 专业领域知识库系统 - 深度分析报告

> 分析日期: 2026-02-23  
> 基于代码底层分析和第一性原理

---

## 一、系统架构全景

你的 RAG 系统是一个**三层架构**的专业领域知识库：

```
┌─────────────────────────────────────────────────────────────────┐
│                        用户查询层                                 │
│  (WebSocket 实时对话 / REST API / OpenAI 兼容接口)              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      RAG 查询引擎                                │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────┐  │
│  │ LlamaIndex      │  │ Query Cache     │  │ Hybrid Search│  │
│  │ (增强检索)      │  │ (查询缓存)      │  │ (混合检索)   │  │
│  └─────────────────┘  └─────────────────┘  └──────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                      数据存储层                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────┐  │
│  │ Milvus       │  │ PostgreSQL   │  │ 文件系统          │  │
│  │ (向量数据库)  │  │ (会话存储)   │  │ (原始文档)        │  │
│  └──────────────┘  └──────────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 二、接口工作原理深度解析

### 2.1 RAG 查询接口群

#### 📌 `POST /rag/llamaindex/query`

**工作流程**:

```
用户查询 "新加坡EP要求"
        ↓
1. 检查 Query Cache (TTL=3600秒)
        ↓ (命中)
直接返回缓存结果
        ↓ (未命中)
2. Qwen3 Embedding 模型生成查询向量
        ↓
3. 连接 Milvus 向量数据库
        ↓
4. 执行向量相似度搜索 (top_k=10)
        ↓
5. 按 source 去重，返回 top 3 上下文
        ↓
6. 生成答案 (基于检索到的上下文)
        ↓
7. 写入 Query Cache
        ↓
返回结果
```

**关键参数**:
- `query`: 用户查询文本
- `sources`: 可选，按指定文档源过滤
- `top_k`: 返回 top k 个结果 (默认 10)
- `use_cache`: 是否使用缓存 (默认 true)

**当前状态**:
```json
{
  "total_entities": 428,    // Milvus 中总向量数
  "cached_queries": 0,      // 当前缓存的查询数
  "embedding_dimensions": 1024  // Qwen3 嵌入维度
}
```

#### 📌 `GET /rag/llamaindex/config`

**功能**: 返回 RAG 系统的配置信息

```json
{
  "features": {
    "hybrid_search": true,      // 混合检索 (向量 + BM25)
    "multiple_chunking": true,  // 多策略分块
    "query_cache": true,        // 查询缓存
    "custom_embeddings": true    // 自定义嵌入
  },
  "chunk_strategies": ["auto", "semantic", "fixed", "code", "markdown"],
  "default_chunk_strategy": "auto",
  "default_top_k": 10
}
```

#### 📌 `GET /rag/llamaindex/stats`

**功能**: 返回 RAG 系统的运行时统计

```json
{
  "index": {
    "collection": "context",
    "milvus_uri": "http://milvus:19530",
    "embedding_dimensions": 1024,
    "total_entities": 428
  },
  "cache": {
    "enabled": true,
    "ttl": 3600,
    "cached_queries": 0
  }
}
```

#### 📌 `POST /rag/llamaindex/cache/clear`

**功能**: 清除查询缓存

---

### 2.2 知识库状态接口群

#### 📌 `GET /knowledge/status`

**这是系统的"健康检查"接口**，返回三层状态：

```
┌────────────────────────────────────────────────────────────┐
│  Layer 1: Config (config.json)                          │
│  - sources: 38 个配置的文档源                            │
│  - selected_sources: 6 个选中的源                        │
└────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────┐
│  Layer 2: Files (/app/uploads/)                         │
│  - total: 38 个上传的文档                                │
│  - 存储在 source_mapping.json 中                         │
└────────────────────────────────────────────────────────────┘
                              ↓
┌────────────────────────────────────────────────────────────┐
│  Layer 3: Vectors (Milvus)                               │
│  - total: 428 个向量条目                                 │
│  - 来自 38 个文档源                                      │
└────────────────────────────────────────────────────────────┘
```

**关键洞察 - issues 字段分析**:

| 字段 | 含义 | 当前状态 |
|------|------|---------|
| `orphaned_in_config` | 配置了但文件丢失 | [] ✅ |
| `untracked_files` | 有文件但未配置 | [] ✅ |
| `need_indexing` | 有文件但无向量 | [] ✅ |
| `orphaned_vectors` | 有向量但文件已删 | [] ✅ |
| `config_without_vectors` | 配置了但向量丢失 | [] ✅ |

**结论**: 你的系统**完全同步**，38 个文档都已正确索引！

#### 📌 `GET /sources/vector-counts`

**功能**: 返回每个文档源的向量数量

```json
{
  "sources": ["doc1.pdf", "doc2.md", ...],  // 38 个源
  "total_vectors": 428,
  "source_vectors": {
    "16_中国制造出海ODI合规_ingstart.html.md": 3,
    // ... 每个源的向量数
  }
}
```

**用途**: 
- 识别哪些文档被正确索引
- 发现索引失败的文档

---

### 2.3 数据流转图

```
文档摄取流程 (POST /ingest):
                                    
  用户上传 PDF/MD/HTML
         ↓
  ┌──────────────────────┐
  │ 1. 文件存储          │
  │    → /app/uploads/   │
  │ 2. 文本提取          │
  │    → UnstructuredLoader
  │    → PyPDF (备选)    │
  └──────────────────────┘
         ↓
  ┌──────────────────────┐
  │ 3. 文本分块          │
  │    chunk_size=1000  │
  │    chunk_overlap=200 │
  └──────────────────────┘
         ↓
  ┌──────────────────────┐
  │ 4. 生成向量          │
  │    → Qwen3 Embedding│
  │    → 1024 维度       │
  └──────────────────────┘
         ↓
  ┌──────────────────────┐
  │ 5. 存入 Milvus      │
  │    → collection:     │
  │      "context"       │
  │    → fields:        │
  │      text, vector,   │
  │      source,          │
  │      file_path        │
  └──────────────────────┘
         ↓
  ┌──────────────────────┐
  │ 6. 更新配置          │
  │    → config.json    │
  │    → source_mapping │
  └──────────────────────┘
```

---

## 三、20+ 深度洞察

### 系统架构洞察

1. **三层数据一致性**: Config → Files → Vectors 必须保持同步，你的系统当前状态完美 ✅

2. **Milvus Collection 设计**: 使用单一 `context` collection 存储所有文档，通过 `source` 字段过滤

3. **向量维度**: Qwen3 生成 1024 维向量 (当前 428 个向量条目)

4. **查询缓存机制**: 基于 SHA256(query + sources) 哈希，TTL 3600 秒，显著加速重复查询

5. **分块策略**: 默认 1000 字符块，200 字符重叠，平衡语义完整性和召回率

### 性能洞察

6. **并行 Embedding**: 已优化为 10 线程并行请求 Embedding 服务

7. **向量搜索度量**: 使用 `IP` (Inner Product) 或 `L2` 距离，默认 IP

8. **查询降级**: 如果 Milvus 查询失败，自动降级到 LangChain VectorStore

9. **缓存命中**: 当前缓存为空 (0 queries)，可能需要更多使用来观察效果

### 数据治理洞察

10. **选中源机制**: 38 个文档中只有 6 个被选中用于 RAG 检索 (`selected_sources`)

11. **源追踪**: `source_mapping.json` 追踪每个源的文件路径

12. **软删除**: 删除源时，从 Milvus 删除向量但不删除原始文件

13. **元数据存储**: 使用 JSONB 存储消息，支持复杂的对话历史

### API 设计洞察

14. **LlamaIndex 增强**: 虽然有 LlamaIndex 接口，但核心还是直接使用 Milvus (简化版)

15. **混合检索预留**: 配置显示支持 hybrid_search，但代码未完全实现 BM25

16. **Chunk 策略**: 支持 auto/semantic/fixed/code/markdown 五种分块策略

17. **Source 过滤**: 查询时支持按 source 过滤，实现多租户/多知识库隔离

### 安全与可靠性洞察

18. **认证机制**: WebSocket 支持 JWT token 认证 (`?token=xxx`)

19. **心跳保活**: 30 秒心跳间隔，90 秒超时断开

20. **错误处理**: 所有接口统一错误响应格式

21. **会话隔离**: 每个 chat_id 独立处理，支持多用户并发

22. **向量化容错**: 单个文档向量生成失败不影响其他文档

---

## 四、实际数据解读

### 当前知识库状态

| 指标 | 数值 |
|------|------|
| 文档总数 | 38 |
| 向量总数 | 428 |
| 平均每个文档向量数 | 11.26 |
| 选中的知识源 | 6 |
| 会话总数 | 21 |

### 知识源分布

从文档名可以看出这是一个 **中国企业出海新加坡合规知识库**：

- 📋 **公司注册**: ACRA 指南
- 💰 **税务**: IRAS 所得税、转让定价
- 👷 **用工**: MOM EP 准证、COMPASS、雇佣法
- 🔒 **数据合规**: PDPA 个人/儿童数据保护
- 🏦 **金融**: 银行、税务指南
- 🌍 **投资**: FDI、房地产、投资统计

---

## 五、使用建议

### 推荐工作流

1. **查询知识库**:
```bash
curl -X POST http://localhost:8000/rag/llamaindex/query \
  -H "Content-Type: application/json" \
  -d '{"query": "新加坡EP薪资要求", "top_k": 5}'
```

2. **检查健康状态**:
```bash
curl -s http://localhost:8000/knowledge/status | python3 -c "
import json, sys
d = json.load(sys.stdin)
print('同步状态:', d['summary']['fully_synced_count'], '/', d['config']['total'])
print('问题:', d['issues'])
"
```

3. **查看向量分布**:
```bash
curl -s http://localhost:8000/sources/vector-counts | python3 -c "
import json, sys
d = json.load(sys.stdin)
sv = d['source_vectors']
print('向量最多的文档:')
for k, v in sorted(sv.items(), key=lambda x: -x[1])[:5]:
    print(f'  {k}: {v}')
"
```

### 监控指标

建议监控:
- `/rag/llamaindex/stats` 中的 `total_entities` 变化
- `/knowledge/status` 中的 `issues` 字段
- `/sources/vector-counts` 中每个源的向量数

---

## 六、架构优化建议

### 短期 (1-2 周)

1. **实现真正的 Hybrid Search**: 当前配置支持但未实现 BM25 检索
2. **添加查询重排序 (Reranking)**: 使用 Cross-Encoder 对结果重排
3. **完善 Chunk 策略**: 根据文档类型选择合适的分块策略

### 中期 (1 个月)

4. **多 Collection 隔离**: 按知识领域分 Collection
5. **增量索引**: 支持文档更新时增量更新向量
6. **监控面板**: 集成 Prometheus + Grafana

### 长期 (3 个月)

7. **多模态 RAG**: 支持图片、表格理解
8. **Agentic RAG**: 让 LLM 自主决定何时检索
9. **知识图谱融合**: 结合 KG 提升推理能力

---

*此分析基于代码底层实现和实际运行数据*
