import Index from "./pages/index";
import NotFound from "./pages/NotFound";
import ChatPage from "./pages/chat/index";
import KnowledgePage from "./pages/knowledge/index";

export const routers = [
  {
    path: "/",
    name: "home",
    element: <Index />,
  },
  {
    path: "/chat",
    name: "chat",
    element: <ChatPage />,
  },
  {
    path: "/knowledge",
    name: "knowledge",
    element: <KnowledgePage />,
  },
  /* ADD ALL CUSTOM ROUTES ABOVE THE CATCH-ALL "*" ROUTE */
  {
    path: "*",
    name: "404",
    element: <NotFound />,
  },
];

declare global {
  interface Window {
    __routers__: typeof routers;
  }
}

window.__routers__ = routers;
