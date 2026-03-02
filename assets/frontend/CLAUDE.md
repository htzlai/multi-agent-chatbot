# CLAUDE.md — Frontend

> Inherits from project root CLAUDE.md. This file adds frontend-specific context.

## Tech Stack

| Category | Technology |
|----------|------------|
| Build Tool | Vite 7 |
| Language | TypeScript |
| Framework | React 19 |
| UI Components | shadcn/ui |
| Styling | Tailwind CSS |
| Routing | React Router DOM |
| Animation | Framer Motion |
| Icons | Lucide React |

## Commands

```bash
# Install dependencies
pnpm install

# Start development server
pnpm dev

# Build for production
pnpm build:prod

# Lint
pnpm lint

# Preview production build
pnpm preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── chat/          # Chat feature components
│   │   ├── knowledge/     # Knowledge management components
│   │   ├── landing/       # Landing page sections
│   │   ├── layout/        # Layout components (Navbar, Footer)
│   │   └── ui/            # shadcn/ui base components
│   ├── hooks/             # Custom React hooks
│   ├── lib/
│   │   ├── api/           # Backend API modules (chats, models, sources, knowledge)
│   │   ├── api-client.ts  # Base fetch wrapper with error handling
│   │   └── utils.ts       # Utility functions
│   ├── pages/             # Route pages (each in its own subdirectory)
│   ├── App.tsx            # Main app component, sets up providers
│   ├── router.tsx         # Router config (createBrowserRouter)
│   ├── main.tsx           # Entry point
│   └── index.css          # Global styles
├── public/                # Static assets
├── package.json
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

## Directory Responsibilities

- **src/components/**: Group by feature domain (`chat/`, `knowledge/`, `landing/`, `layout/`). `ui/` holds shadcn/ui base components.
- **src/hooks/**: One hook per file, single responsibility.
- **src/lib/api/**: One API client module per backend domain (chats, models, sources, knowledge). `api-client.ts` provides the base fetch wrapper.
- **src/pages/**: Each page gets its own subdirectory with `index.tsx` as entry point.
- **src/router.tsx**: All routes registered via `createBrowserRouter`.

## How to Add New Code

### New Page
1. Create `src/pages/<name>/index.tsx`
2. Register route in `src/router.tsx`:
   ```tsx
   import MyPage from "./pages/my-page";
   // inside createBrowserRouter routes array:
   { path: "/my-page", element: <MyPage /> }
   ```

### New Component
- Feature-specific → `src/components/<feature>/`
- Page-specific → `src/pages/<page>/`
- Reusable UI primitive → `src/components/ui/`

### New Hook
- `src/hooks/use-<name>.ts` — one export per file

### New API Module
- `src/lib/api/<domain>.ts` — one file per backend domain

## Coding Conventions

- **One module, one responsibility** — keep files small and focused
- **PascalCase** for components; **camelCase** for hooks and utilities
- **Immutable state updates** — never mutate React state directly
- **High cohesion, low coupling** — share code via `components/`, `hooks/`, or `lib/` only when truly reusable
- **Keep this file updated** when adding/removing modules or pages
