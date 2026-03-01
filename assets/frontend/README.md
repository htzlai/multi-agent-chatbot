# Frontend Project

A modern React + TypeScript web application with shadcn/ui components.

---

## Tech Stack

| Category | Technology |
|----------|------------|
| Build Tool | Vite |
| Language | TypeScript |
| Framework | React 19 |
| UI Components | shadcn/ui |
| Styling | Tailwind CSS |
| Routing | React Router DOM |
| Data Fetching | TanStack Query |
| Animation | Framer Motion |
| Icons | Lucide React |

---

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── chat/          # Chat feature components
│   │   ├── landing/       # Landing page components
│   │   ├── layout/        # Layout components (Navbar, Footer)
│   │   └── ui/            # shadcn/ui components
│   ├── hooks/             # Custom React hooks
│   ├── lib/               # Utilities and mock data
│   └── pages/             # Route pages
├── public/                # Static assets
├── package.json
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

---

## Getting Started

```bash
# Install dependencies
pnpm install

# Start development server
pnpm dev

# Build for production
pnpm build:prod
```

---

## Available Scripts

| Command | Description |
|---------|-------------|
| `pnpm dev` | Start development server on port 8080 |
| `pnpm build` | Build for development |
| `pnpm build:prod` | Build for production |
| `pnpm lint` | Run ESLint |
| `pnpm preview` | Preview production build |
