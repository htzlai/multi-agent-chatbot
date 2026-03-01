import { useState, useCallback, useRef } from "react";
import { templates } from "@/lib/mock-templates";

export interface CodeBlock {
  language: string;
  code: string;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  codeBlocks?: CodeBlock[];
  previewHtml?: string;
  timestamp: Date;
}

export interface Conversation {
  id: string;
  title: string;
  updatedAt: Date;
}

const mockResponses: Record<string, { text: string; templateId: string }> = {
  dashboard: {
    text: "I've built an analytics dashboard with KPI metric cards, a bar chart visualization, and a sidebar navigation. The dashboard includes revenue, users, orders, and conversion rate metrics with trend indicators.",
    templateId: "dashboard",
  },
  blog: {
    text: "Here's a modern blog layout with a clean hero section, article cards in a responsive grid, and beautiful gradient thumbnails. The design emphasizes readability and visual hierarchy.",
    templateId: "blog",
  },
  ecommerce: {
    text: "I've created an e-commerce storefront with a product grid, category navigation, a promotional banner, and product cards with pricing. The design is clean and conversion-focused.",
    templateId: "ecommerce",
  },
  store: {
    text: "I've created an e-commerce storefront with a product grid, category navigation, a promotional banner, and product cards with pricing. The design is clean and conversion-focused.",
    templateId: "ecommerce",
  },
  portfolio: {
    text: "Here's an elegant portfolio website with a bold hero introduction, a selected works grid with hover overlays, and a minimalist aesthetic perfect for showcasing creative work.",
    templateId: "portfolio",
  },
  landing: {
    text: "I've built a high-converting SaaS landing page with a hero section, feature grid, three-tier pricing table, and clear CTAs. The design follows modern SaaS best practices.",
    templateId: "landing",
  },
  saas: {
    text: "Here's a SaaS application interface with sidebar navigation, a project listing table with status badges, and action buttons. It's a solid foundation for any web application.",
    templateId: "saas-app",
  },
  app: {
    text: "Here's a SaaS application interface with sidebar navigation, a project listing table with status badges, and action buttons. It's a solid foundation for any web application.",
    templateId: "saas-app",
  },
};

const defaultResponse = {
  text: "I've generated a clean SaaS landing page based on your description. It includes a navigation bar, hero section with CTA, feature grid, and a pricing section. You can preview it on the right and customize further.",
  templateId: "landing",
};

const mockConversations: Conversation[] = [
  { id: "1", title: "Dashboard with charts", updatedAt: new Date(Date.now() - 1000 * 60 * 30) },
  { id: "2", title: "Blog redesign", updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 2) },
  { id: "3", title: "E-commerce store", updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 24) },
  { id: "4", title: "Portfolio website", updatedAt: new Date(Date.now() - 1000 * 60 * 60 * 48) },
];

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [previewHtml, setPreviewHtml] = useState("");
  const [conversations] = useState<Conversation[]>(mockConversations);
  const [activeConversation, setActiveConversation] = useState<string | null>(null);
  const idCounter = useRef(0);

  const genId = () => {
    idCounter.current += 1;
    return `msg-${idCounter.current}-${Date.now()}`;
  };

  const sendMessage = useCallback((text: string) => {
    const userMsg: ChatMessage = {
      id: genId(),
      role: "user",
      content: text,
      timestamp: new Date(),
    };

    setMessages((prev) => [...prev, userMsg]);
    setIsLoading(true);

    // simulate AI response
    setTimeout(() => {
      const lowerText = text.toLowerCase();
      let matched = defaultResponse;

      for (const [keyword, response] of Object.entries(mockResponses)) {
        if (lowerText.includes(keyword)) {
          matched = response;
          break;
        }
      }

      const template = templates.find((t) => t.id === matched.templateId);
      const html = template?.previewHtml ?? "";

      const assistantMsg: ChatMessage = {
        id: genId(),
        role: "assistant",
        content: matched.text,
        previewHtml: html,
        codeBlocks: [
          {
            language: "html",
            code: html.slice(0, 600) + "\n  <!-- ... more code ... -->",
          },
        ],
        timestamp: new Date(),
      };

      setMessages((prev) => [...prev, assistantMsg]);
      setPreviewHtml(html);
      setIsLoading(false);
    }, 1500 + Math.random() * 1000);
  }, []);

  const selectTemplate = useCallback((templateId: string) => {
    const template = templates.find((t) => t.id === templateId);
    if (template) {
      setPreviewHtml(template.previewHtml);

      const msg: ChatMessage = {
        id: genId(),
        role: "assistant",
        content: `Loaded the "${template.name}" template. You can preview it on the right. Feel free to ask me to customize any part of it.`,
        previewHtml: template.previewHtml,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, msg]);
    }
  }, []);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setPreviewHtml("");
  }, []);

  return {
    messages,
    isLoading,
    previewHtml,
    conversations,
    activeConversation,
    setActiveConversation,
    sendMessage,
    selectTemplate,
    setPreviewHtml,
    clearMessages,
  };
}
