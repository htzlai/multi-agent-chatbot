# Code Guideline

## Project Structure Overview

```
project-root/
  ├── public/                # Static assets (favicon, robots.txt, etc.)
  ├── src/
  │   ├── components/        # All reusable UI components
  │   │   ├── chat/          # Chat feature components
  │   │   ├── knowledge/     # Knowledge management components
  │   │   ├── landing/       # Landing page sections
  │   │   ├── layout/        # Layout components (Navbar, Footer)
  │   │   └── ui/            # shadcn/ui base components
  │   ├── hooks/             # Custom React hooks
  │   ├── lib/               # Utilities and API clients
  │   │   └── api/           # Backend API modules (chats, models, sources, knowledge)
  │   ├── pages/             # Application pages (each page in its own subdirectory)
  │   ├── App.tsx            # Main app component, sets up providers
  │   ├── router.tsx         # Router config (createBrowserRouter)
  │   ├── main.tsx           # Entry point for the React app
  │   └── index.css          # Global styles
  ├── package.json           # Project metadata and scripts
  ├── tailwind.config.ts     # Tailwind CSS configuration
  └── ...                    # Other config and lock files
```

## Directory Responsibilities

- **public/**: Static files served directly. Place images, icons, and robots.txt here.
- **src/components/**: All UI components.
  - **ui/**: Contains atomic and composite UI components (shadcn/ui).
  - *Group related components into subdirectories by feature domain (e.g., `chat/`, `knowledge/`, `landing/`).*
- **src/hooks/**: Custom React hooks. Each file should export a single hook focused on one responsibility.
- **src/lib/**: Utility functions and API clients.
  - **api/**: Backend API modules — one file per domain (chats, models, sources, knowledge).
  - **api-client.ts**: Base fetch wrapper with error handling.
- **src/pages/**: All route-level pages.
  - *Each page should have its own subdirectory if it contains more than a single file.*
- **src/router.tsx**: Sets up routing via `createBrowserRouter`.
- **src/main.tsx**: Application entry point.

**Important:**
Whenever a new module (such as a component, hook, or utility) or a new page is added or removed, this document **must be updated immediately** to reflect the changes. Keeping this documentation up to date ensures that all collaborators have a clear understanding of the current project structure and its intended organization.

## How to Add New Code

### 1. Adding a New Page

- **Create a subdirectory under `src/pages/` for each new page.**
  - Example: For a "Dashboard" page, create `src/pages/dashboard/`.
- **Place the main page component as `index.tsx` inside the subdirectory.**
- **Add any page-specific components or logic in the same subdirectory.**
- **Register the new route in `src/router.tsx`.**
  - Example:
    ```tsx
    import Dashboard from "./pages/dashboard";
    // inside createBrowserRouter routes array:
    {
      path: "/dashboard",
      element: <Dashboard />
    }
    ```

### 2. Adding a New Component

- **If you are adding a group of related components, create a subdirectory (e.g., `form/`, `charts/`).**
- **If the component is only used by a specific page, place it in that page's subdirectory under `src/pages/`.**
- **Each component should be focused on a single responsibility.**
- **Small files (< 100 lines) are encouraged for a single component.**

### 3. Adding a New Hook

- **Create a new file in `src/hooks/` named after the hook (e.g., `use-feature.ts`).**
- **Each file should export only one hook.**
- **Hooks should be as small and focused as possible.**

### 4. Adding Utilities

- **Add utility functions to `src/lib/`.**
- **Add API client modules to `src/lib/api/` — one file per domain.**

## Coding Best Practices

- **One module, one responsibility:**
  Each file (component, hook, utility) should do one thing only.
- **High cohesion, low coupling:**
  Keep related logic together and avoid unnecessary dependencies between modules.
- **Naming conventions:**
  - Use `PascalCase` for components and page directories.
  - Use `camelCase` for hooks and utility functions.
  - Name page subdirectories and files after their route or feature.
- **Component structure:**
  - Keep components small and focused.
  - Extract subcomponents if a component grows too large.
- **Page structure:**
  - Place all logic, hooks, and components specific to a page in its subdirectory.
  - Only share code via `components/`, `hooks/`, or `lib/` if it is truly reusable.
