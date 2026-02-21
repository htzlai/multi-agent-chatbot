# Supabase Auth 集成 - 设置指南

## 快速开始

### 1. Supabase Cloud 配置

1. 登录 [Supabase Dashboard](https://supabase.com/dashboard)
2. 创建新项目或使用现有项目
3. 获取配置信息：
   - `Project URL`: Settings → API → Project URL
   - `Anon Key`: Settings → API → Project API keys → anon public
   - `JWT Secret`: Settings → API → JWT Secret

### 2. 前端配置 (molycure-frontend)

```bash
cd /home/htzl/molycure-frontend

# 安装依赖
pnpm add @supabase/ssr @supabase/supabase-js

# 创建环境变量文件
cat > .env.local << 'EOF'
# Supabase Cloud
NEXT_PUBLIC_SUPABASE_URL=https://your-project-ref.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-anon-key

# Backend URL
NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
NEXT_PUBLIC_USE_MOLYCURE_BACKEND=true
EOF

# 启动开发服务器
pnpm dev
```

### 3. 后端配置

```bash
cd /home/htzl/dgx-spark-playbooks/nvidia/multi-agent-chatbot/assets/backend

# 安装依赖
pip install python-jose[cryptography] httpx

# 添加环境变量到 .env 或 docker-compose.yml
SUPABASE_JWT_SECRET=your-jwt-secret
```

### 4. 营销网站配置 (molycure.tech-ai-site)

```bash
cd /home/htzl/molycure.tech-ai-site

# 创建环境变量文件
cat > .env.local << 'EOF'
# Chat Application URL
NEXT_PUBLIC_CHAT_URL=http://localhost:3000
EOF

# 安装依赖
npm install

# 启动开发服务器
npm run dev
```

## 测试清单

### ✅ 前端认证测试

| 测试项 | 预期结果 |
|--------|----------|
| 访问 `/login` | 显示登录页面，有 Google/GitHub 按钮 |
| 使用邮箱注册 | 成功注册，收到确认邮件（如启用） |
| 使用邮箱登录 | 成功登录，跳转到主页 |
| 使用 Google OAuth | 跳转到 Google 授权页面 |
| 使用 GitHub OAuth | 跳转到 GitHub 授权页面 |
| 访问 `/auth/callback` | 正确处理 OAuth 回调 |
| 登出 | 成功登出，跳转到登录页 |

### ✅ API 认证测试

```bash
# 获取访问令牌 (登录后从浏览器控制台执行)
const { data: { session } } = await supabase.auth.getSession()
console.log(session.access_token)

# 测试 API 调用
curl -H "Authorization: Bearer YOUR_TOKEN" \
  http://localhost:8000/sources
```

### ✅ WebSocket 认证测试

打开浏览器控制台：

```javascript
// 连接 WebSocket (带 token)
const ws = new WebSocket('ws://localhost:8000/ws/chat/test-chat-id?token=YOUR_TOKEN')
ws.onopen = () => console.log('Connected!')
ws.onmessage = (e) => console.log('Message:', e.data)
```

### ✅ 内嵌聊天测试

1. 启动 molycure.tech-ai-site: `npm run dev`
2. 访问 http://localhost:3001
3. 滚动到 "AI Chat Section"
4. 点击 "开始对话" 按钮
5. 验证 iframe 加载聊天应用

## 架构概览

```
┌─────────────────────────────────────────────────────────────────────┐
│                     molycure.tech (营销网站)                         │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  EmbeddedChatPanel (iframe)                                   │  │
│  │  ↓ 加载                                                        │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│                chat.molycure.tech (molycure-frontend)               │
│  ┌──────────────┐  ┌─────────────────────────────────────────────┐  │
│  │   Sidebar    │  │  Chat Area                                  │  │
│  │   - History  │  │  - WebSocket → Backend                      │  │
│  │   - Settings │  │  - REST API → Backend                       │  │
│  └──────────────┘  └─────────────────────────────────────────────┘  │
│         │                                                           │
│         │ Supabase Auth                                             │
│         ▼                                                           │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  Supabase Cloud (Auth)                                       │   │
│  │  - 用户注册/登录                                              │   │
│  │  - OAuth 提供商                                               │   │
│  │  - JWT 令牌签发                                               │   │
│  └──────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
                                │
                                │ JWT in Authorization header
                                ▼
┌─────────────────────────────────────────────────────────────────────┐
│              FastAPI Backend (localhost:8000)                       │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │  auth.py - JWT 验证中间件                                     │   │
│  │  - 可选认证 (未配置时开放)                                     │   │
│  │  - WebSocket token 验证                                       │   │
│  └──────────────────────────────────────────────────────────────┘   │
│         │                                                           │
│         ▼                                                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  PostgreSQL  │  │   Milvus    │  │  LangGraph Agent          │  │
│  │  会话存储    │  │   向量存储  │  │  RAG + Multi-Agent        │  │
│  └──────────────┘  └──────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

## 文件清单

### 新增文件

| 位置 | 文件 | 说明 |
|------|------|------|
| molycure-frontend | `lib/supabase/client.ts` | 浏览器 Supabase 客户端 |
| molycure-frontend | `lib/supabase/server.ts` | 服务端 Supabase 客户端 |
| molycure-frontend | `lib/supabase/middleware.ts` | 会话刷新处理 |
| molycure-frontend | `lib/supabase/auth.ts` | 认证帮助函数 |
| molycure-frontend | `lib/supabase/index.ts` | 导出模块 |
| molycure-frontend | `middleware.ts` | Next.js 中间件 |
| molycure-frontend | `app/auth/callback/route.ts` | OAuth 回调 |
| backend | `auth.py` | JWT 验证中间件 |
| molycure.tech-ai-site | `src/components/chat/EmbeddedChatPanel.tsx` | 内嵌聊天组件 |
| molycure.tech-ai-site | `.env.example` | 环境变量模板 |

### 修改文件

| 位置 | 文件 | 修改内容 |
|------|------|----------|
| molycure-frontend | `app/(auth)/actions.ts` | 替换为 Supabase Auth |
| molycure-frontend | `app/(auth)/login/page.tsx` | 支持 OAuth 按钮 |
| molycure-frontend | `app/(auth)/register/page.tsx` | 使用 Supabase 注册 |
| molycure-frontend | `app/layout.tsx` | 移除 NextAuth SessionProvider |
| molycure-frontend | `lib/api/backend-client.ts` | 添加 JWT 到请求头 |
| molycure-frontend | `hooks/use-molycure-chat.ts` | WebSocket JWT 认证 |
| molycure-frontend | `.env.example` | 添加 Supabase 变量 |
| backend | `main.py` | 可选 WebSocket 认证 |
| molycure.tech-ai-site | `src/app/page.tsx` | 添加聊天面板 section |

## 常见问题

### Q: 后端认证是否必须配置？
A: 不必须。如果 `SUPABASE_JWT_SECRET` 未配置，后端将保持开放状态。

### Q: 如何启用 Google OAuth？
A: 在 Supabase Dashboard → Authentication → Providers → 启用 Google，配置 OAuth Client ID 和 Secret。

### Q: 如何启用微信登录？
A: Supabase 企业版支持微信登录。需要在 Supabase Dashboard 配置微信 OAuth。

### Q: iframe 嵌入跨域问题？
A: 确保 molycure-frontend 的 CORS 配置允许 molycure.tech 域名访问。
