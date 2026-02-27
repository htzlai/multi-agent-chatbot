# Chatbot Spark 项目分析 - Claude Code 配置建议

## 一、项目翻译

### 1.1 项目概述

**Chatbot Spark** 是一个基于 DGX Spark 构建的本地多智能体系统。凭借 128GB 统一内存，DGX Spark 可以运行多LLM 和 VLM，实现跨智能体交互。

核心是一个由 GPT-OSS-120B 驱动的监督智能体（supervisor agent），协调专门的下游智能体，用于：
- 检索增强生成（RAG）
- 编码（Coding）

### 1.2 核心特性

| 特性 | 说明 |
|------|------|
| **MCP Server 集成** | 通过简单的多服务器客户端连接自定义 MCP 服务器 |
| **工具调用** | 使用 agents-as-tools 框架，可创建连接为工具的额外智能体 |
| **易更换模型** | 使用 Llama CPP 和 Ollama，通过 OpenAI API 提供服务 |
| **向量索引与检索** | GPU 加速的 Milvus，实现高性能文档检索 |
| **实时 LLM 流式输出** | 自定义基础设施，支持流式监督智能体响应 |
| **gpt-oss 集成** | 默认使用 gpt-oss:120b 作为聊天/工具调用模型 |

### 1.3 默认模型配置

| 模型 | 量化 | 类型 | 显存 |
|------|------|------|------|
| GPT-OSS:120B | MXFP4 | Chat | ~63.5 GB |
| Deepseek-Coder:6.7B-Instruct | Q8 | Coding | ~9.5 GB |
| Qwen3-Embedding-4B | Q8 | Embedding | ~5.39 GB |

**总显存需求：约 78 GB**

---

## 二、项目技术栈总结

```
┌─────────────────────────────────────────┐
│           Chatbot Spark                 │
├─────────────────────────────────────────┤
│  框架:   FastAPI + LangGraph           │
│  AI:     GPT-OSS-120B, Deepseek-Coder  │
│  VLM:    Qwen2.5-VL:7B                 │
│  Embedding: Qwen3-Embedding-4B         │
│  向量库: Milvus (GPU 加速)              │
│  数据库: PostgreSQL                     │
│  前端:   Next.js                       │
│  部署:   Docker + Docker Compose        │
└─────────────────────────────────────────┘
```

---

## 三、项目 Claude Code 配置建议

### 3.1 推荐的 Skills（基于项目技术栈）

| Skill | 用途 | 优先级 |
|-------|------|--------|
| `tdd-workflow/` | 测试驱动开发 | ⭐⭐⭐ |
| `python-patterns/` | Python 最佳实践 | ⭐⭐⭐ |
| `python-testing/` | Python 测试 | ⭐⭐⭐ |
| `backend-patterns/` | 后端 API 模式 | ⭐⭐⭐ |
| `api-design/` | API 设计规范 | ⭐⭐⭐ |
| `docker-patterns/` | Docker 配置 | ⭐⭐⭐ |
| `database-migrations/` | 数据库迁移 | ⭐⭐ |
| `postgres-patterns/` | PostgreSQL 模式 | ⭐⭐ |
| `security-review/` | 安全审查 | ⭐⭐ |
| `coding-standards/` | 编码标准 | ⭐⭐ |


在 `assets/backend/CLAUDE.md` 中添加：

```markdown
# Chatbot Spark 项目配置

## 技术栈
- 语言: Python 3.11+
- 框架: FastAPI + LangGraph
- AI: GPT-OSS-120B, Deepseek-Coder
- 向量库: Milvus (GPU)
- 数据库: PostgreSQL
- 部署: Docker Compose

## 推荐 Skills
- t
```

---

## 四、MCP 服务器配置建议

项目使用的 MCP 服务器（根据 backend/client.py）：

| MCP Server | 用途 |
|------------|------|
| rag-server | RAG 检索 |
| code-generation-server | 代码生成 |
| weather-server | 天气测试 |
