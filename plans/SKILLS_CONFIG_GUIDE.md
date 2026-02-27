

# Skills 使用指南与配置建议

## 一、Skills 工作原理

### 1.1 Skills 是什么

**Skills（技能）** 是预定义的工作流定义，当需要执行特定工作流时作为提示词使用。它们类似于"快捷方式"，让 Claude Code 能够快速调用预设的提示词模板。

### 1.2 Skills 是自动调用吗

**不完全自动调用**。根据官方文档：

| 调用方式 | 说明 |
|----------|------|
| **手动调用** | 通过 `/skill-name` 斜杠命令调用 |
| **上下文触发** | Claude 根据对话上下文自动建议使用相关 skill |
| **命令集成** | 部分 skills 作为 commands 集成，可直接执行 |

### 1.3 Skills vs Commands

```
~/.claude/skills/     # 更广泛的工作流定义
~/.claude/commands/   # 快速可执行的提示词
```

两者有重叠，但存储方式不同。

---

## 二、官方推荐配置数量

### 2.1 MCP 服务器数量（重要参考）

根据官方文档的**关键警告**：

> **上下文窗口管理**
> 你的 200k 上下文窗口在压缩前可能只有 70k（如果启用了太多工具）。

**经验法则：**
- 配置 20-30 个 MCP
- **每个项目保持启用少于 10 个**
- 活动工具少于 80 个

### 2.2 Skills 数量建议

官方作者的实际配置：
- **Plugins**: 通常只启用 4-5 个
- **Subagents**: 约 9 个（已足够）
- **Rules**: 约 8 个模块化规则

**对于你的项目：**
- 117 个 Skills 确实**过多**
- 建议保留 **10-15 个**核心 Skills
- 其他按需启用

---

## 三、你的项目推荐 Skills（Python/FastAPI 后端）

### 3.1 核心推荐 Skills（必须保留）

| Skill 名称 | 用途 | 优先级 |
|------------|------|--------|
| `tdd` | 测试驱动开发 | ⭐⭐⭐ |
| `tdd-workflow` | TDD 工作流 | ⭐⭐⭐ |
| `python-patterns` | Python 最佳实践 | ⭐⭐⭐ |
| `python-testing` | Python 测试模式 | ⭐⭐⭐ |
| `python-review` | Python 代码审查 | ⭐⭐⭐ |
| `backend-patterns` | 后端 API 模式 | ⭐⭐⭐ |
| `api-design` | API 设计规范 | ⭐⭐ |
| `database-migrations` | 数据库迁移 | ⭐⭐ |
| `docker-patterns` | Docker 配置 | ⭐⭐ |
| `security-review` | 安全审查 | ⭐⭐ |
| `code-review` | 通用代码审查 | ⭐⭐ |

### 3.2 可选 Skills（按需启用）

| Skill 名称 | 用途 | 场景 |
|------------|------|------|
| `postgres-patterns` | PostgreSQL 模式 | 使用 Postgres 时 |
| `deployment-patterns` | 部署模式 | 部署时 |
| `coding-standards` | 编码标准 | 通用 |
| `refactor-clean` | 死代码清理 | 清理时 |
| `verify` | 验证测试 | 验证时 |
| `checkpoint` | 保存检查点 | 重要节点 |

### 3.3 不推荐的 Skills（可以删除）

根据你的项目技术栈，以下 Skills 与你无关：

| Skill | 原因 |
|-------|------|
| `swift-*` | iOS 开发，无需 |
| `golang-*` | Go 开发，无需 |
| `cpp-*` | C++ 开发，无需 |
| `java-*` / `jpa-*` | Java 开发，无需 |
| `springboot-*` | Spring 开发，无需 |
| `django-*` | Django 开发，无需 |
| `react-*` / `frontend-*` | 前端开发，无需 |
| `clickhouse-io` | ClickHouse，无需 |
| `regex-vs-llm-*` | 高级主题，无需 |
| `nutrient-document-*` | 垂直领域，无需 |

---

## 四、如何修改 Skills 数量

### 4.1 查看当前 Skills 列表

```bash
ls ~/.claude/skills/
# 或
ls ~/.claude/commands/
```

### 4.2 精简步骤

1. **创建精选目录**
```bash
mkdir -p ~/.claude/skills-selected
```

2. **复制需要的 Skills**
```bash
# 核心 Skills
cp ~/.claude/skills/tdd.md ~/.claude/skills-selected/
cp ~/.claude/skills/tdd-workflow.md ~/.claude/skills-selected/
cp ~/.claude/skills/python-patterns.md ~/.claude/skills-selected/
cp ~/.claude/skills/python-testing.md ~/.claude/skills-selected/
cp ~/.claude/skills/backend-patterns/ ~/.claude/skills-selected/ -r
cp ~/.claude/skills/api-design.md ~/.claude/skills-selected/
cp ~/.claude/skills/database-migrations.md ~/.claude/skills-selected/
cp ~/.claude/skills/docker-patterns.md ~/.claude/skills-selected/
cp ~/.claude/skills/security-review/ ~/.claude/skills-selected/ -r
```

3. **更新 CLAUDE.md 配置**

在项目 CLAUDE.md 中添加：
```markdown
## 启用的 Skills

本项目只使用以下 Skills：
- tdd / tdd-workflow - 测试驱动开发
- python-patterns - Python 最佳实践
- python-testing - 测试模式
- backend-patterns - 后端 API 模式
- api-design - API 设计规范
- database-migrations - 数据库迁移
- docker-patterns - Docker 配置
- security-review - 安全检查
```

---

## 五、MCP 服务器配置建议

### 5.1 当前问题

你的 MCP 列表显示：
- 117 个 Skills
- 可能还有大量 MCP 服务器

### 5.2 推荐配置

在 `~/.claude.json` 中配置：

```json
{
  "mcpServers": {
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"]
    },
    "firecrawl": {
      "command": "npx", 
      "args": ["-y", "firecrawl-mcp"]
    },
    "postgres": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-postgres", "--", "postgresql://user:pass@localhost/db"]
    }
  },
  "projects": {
    "multi-agent-chatbot": {
      "disabledMcpServers": ["github", "firecrawl", "其他不需要的"]
    }
  }
}
```

### 5.3 检查和管理 MCP

```bash
# 查看当前 MCP 状态
/mcp

# 在 Claude Code 中使用
/plugins
# 然后滚动到 MCP 部分查看启用状态
```

---

## 六、快速参考表

### 6.1 你需要的 Skills（15 个）

```
├── tdd                          # 测试驱动开发
├── tdd-workflow                 # TDD 工作流详细
├── python-patterns              # Python 模式
├── python-testing               # Python 测试
├── python-review                # Python 审查
├── backend-patterns             # ⭐ 后端 API 模式
├── api-design                   # API 设计
├── database-migrations          # DB 迁移
├── docker-patterns               # Docker
├── security-review              # 安全审查
├── coding-standards             # 编码标准
├── code-review                  # 代码审查
├── verify                       # 验证测试
├── checkpoint                   # 检查点
└── refactor-clean              # 清理
```

### 6.2 你不需要的 Skills（可删除 100+ 个）

```
❌ swift-protocol-di-testing
❌ swift-actor-persistence
❌ golang-patterns
❌ golang-testing
❌ go-review
❌ go-build
❌ go-test
❌ cpp-coding-standards
❌ cpp-testing
❌ java-coding-standards
❌ jpa-patterns
❌ springboot-patterns
❌ springboot-security
❌ springboot-tdd
❌ springboot-verification
❌ django-patterns
❌ django-security
❌ django-verification
❌ django-tdd
❌ frontend-patterns
❌ clickhouse-io
❌ regex-vs-llm-structured-text
❌ nutrient-document-processing
❌ cost-aware-llm-pipeline
❌ ... (其他不相关)
```

---

## 七、下一步行动

1. **运行 `/skills` 查看当前列表**
2. **创建精选 Skills 目录**
3. **复制需要的 15 个 Skills**
4. **更新 CLAUDE.md 配置**
5. **检查 MCP 配置，禁用不需要的**

---

*最后更新：2026-02-27*
