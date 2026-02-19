# Langfuse 集成说明与故障排查

本文档汇总 Langfuse 集成的所有改动与配置位置，便于后期故障排查。

---

## 一、已完成项汇总

### 1. 依赖

| 项目 | 位置 | 说明 |
|------|------|------|
| Langfuse SDK | [backend/pyproject.toml](pyproject.toml) | 新增 `langfuse>=2.0.0` |

### 2. 新增文件

| 文件 | 说明 |
|------|------|
| [backend/langfuse_client.py](../langfuse_client.py) | 单例 Langfuse 客户端，读取 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` / `LANGFUSE_BASE_URL`，未配置时返回 `None` |
| [backend/.env.example](../.env.example) | 环境变量示例，含 Langfuse 三项 |
| backend/docs/LANGFUSE_INTEGRATION.md | 本说明与故障排查文档 |

### 3. 代码改动

| 文件 | 改动要点 |
|------|----------|
| [backend/agent.py](../agent.py) | 导入 `get_langfuse_client`；`query()` 开始时创建 trace（`chat_query`），结束时 `trace.end()`；`generate()` 内创建 generation（`llm`）并 `generation.end(output=...)`；使用 `_current_trace` 传递 trace |
| [backend/tools/mcp_servers/rag.py](../tools/mcp_servers/rag.py) | 导入 `get_langfuse_client`；`search_documents()` 创建 trace（`rag_search_documents`），设置 `rag_agent._current_trace`；`retrieve()` 创建 span（`rag_retrieve`）；`generate()` 创建 generation（`rag_generate`）；finally 中清除 `_current_trace` |

### 4. 配置

| 项目 | 位置 | 说明 |
|------|------|------|
| Backend 环境变量 | [assets/docker-compose.yml](../../docker-compose.yml) 的 `backend.environment` | `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL`（空则不上报） |
| Langfuse 容器 | [assets/docker-compose.yml](../../docker-compose.yml) 的 `langfuse` 服务 | 端口 **3105:3000**，依赖 postgres，需先建库 `langfuse` |

---

## 二、3105 端口与 Langfuse 容器配置位置

- **端口 3105**：Langfuse Web UI 映射在 **chatbot 项目的 docker-compose** 中，不是 docker-log。
- **配置位置**：`dgx-spark-playbooks/nvidia/multi-agent-chatbot/assets/docker-compose.yml`，服务名 `langfuse`，映射 `3105:3000`。

与 docker-log（Vector / Loki / Grafana / MCP / AI Alerter）的关系：

- **docker-log**：负责基础设施日志与告警，不包含 Langfuse。
- **chatbot compose**：负责 Backend、Postgres、Milvus、Langfuse 等；Backend 与 Langfuse 同网，便于上报 trace。

---

## 三、完整配置清单（推荐顺序）

所有配置写在 **`assets/.env`**。Compose 只会自动加载同目录下的 **`.env`**，不会加载 `.evn`；若你之前写在 `.evn`，请重命名为 `.env` 或把内容合并进 `.env`。

| 步骤 | 操作 |
|------|------|
| 1 | 在 postgres 中创建库：`docker exec -it postgres psql -U chatbot_user -d chatbot -c "CREATE DATABASE langfuse;"` |
| 2 | 在 `assets/.env` 中配置 **Langfuse 容器用**变量：`LANGFUSE_NEXTAUTH_SECRET`、`LANGFUSE_SALT`、`LANGFUSE_NEXTAUTH_URL`（可参考 `assets/.env.example`） |
| 3 | 启动：`docker compose up -d`，浏览器打开 http://localhost:3105 → 创建项目 → 设置 → API Keys 中复制 Public Key 与 Secret Key |
| 4 | 在同一 `assets/.env` 中配置 **Backend 上报用**变量：`LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL=http://langfuse:3000`，然后重启 backend：`docker compose restart backend` |

---

## 四、后续配置细节（放哪里、怎么配）

### 1. 自托管 Langfuse（端口 3105）

- **放哪里**：已在 **chatbot** 的 [assets/docker-compose.yml](../../docker-compose.yml) 中新增 `langfuse` 服务。
- **首次使用**：在 postgres 中创建 Langfuse 用的库：

```bash
docker exec -it postgres psql -U chatbot_user -d chatbot -c "CREATE DATABASE langfuse;"
```

- **环境变量**（可在宿主机 `.env` 或 compose 中设置）：
  - `LANGFUSE_NEXTAUTH_SECRET`：生产环境必改，用于 Console JWT。
  - `LANGFUSE_SALT`：生产环境必改。
  - `LANGFUSE_NEXTAUTH_URL`：浏览器访问地址，例如 `http://localhost:3105` 或你的域名。

### 2. Backend 上报到 Langfuse

- **放哪里**：在运行 backend 的环境（如宿主机 `.env` 或 compose 的 `backend.environment`）中配置。
- **变量**（已在 [docker-compose.yml](../../docker-compose.yml) 的 backend 中预留）：
  - `LANGFUSE_PUBLIC_KEY`：在 Langfuse 项目设置中复制。
  - `LANGFUSE_SECRET_KEY`：同上。
  - `LANGFUSE_BASE_URL`：自托管填 `http://langfuse:3000`（同 compose 内）；Langfuse Cloud 用其提供的 URL。

### 3. 使用 Langfuse Cloud（不跑 3105 容器）

- 不启动 `langfuse` 服务即可。
- 在 backend 环境变量中只配 `LANGFUSE_PUBLIC_KEY`、`LANGFUSE_SECRET_KEY`、`LANGFUSE_BASE_URL`（Cloud 提供的），不配则无 trace。

---

## 五、故障排查

| 现象 | 可能原因 | 处理 |
|------|----------|------|
| 控制台无 trace | 未配 `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | 在 backend 环境变量中配置并重启 backend |
| 有 key 仍无 trace | `LANGFUSE_BASE_URL` 错误或 Langfuse 未启动 | 自托管时填 `http://langfuse:3000`，确认 `docker ps` 有 langfuse，且 3105 可访问 |
| Langfuse 容器启动报错 | 未创建 `langfuse` 数据库 | 执行上文 `CREATE DATABASE langfuse;` |
| 仅 RAG 无 trace | MCP 进程未加载新代码或未配 key | 确认 rag 所在进程与 backend 使用相同 env，并重启 MCP / backend |

---

## 六、端口与文档对照

| 端口 | 服务 | 所属项目 | 配置文件 |
|------|------|----------|----------|
| 3100 | Grafana | docker-log | Documents/tools/docker-log/docker-compose.yml |
| 3101 | Loki | docker-log | 同上 |
| 3102 | Vector | docker-log | 同上 |
| 3103 | MCP Grafana | docker-log | 同上 |
| 3104 | AI Alerter | docker-log | 同上 |
| **3105** | **Langfuse** | **chatbot** | **dgx-spark-playbooks/.../assets/docker-compose.yml** |
| 8000 | Backend | chatbot | 同上 |
