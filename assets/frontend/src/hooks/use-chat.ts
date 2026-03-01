import { useState, useCallback, useRef, useEffect } from "react";
import {
  listChats,
  createChat,
  deleteChat,
  getChatMessages,
  getChatMetadata,
  streamCompletion,
  stopGeneration,
  type RawMessage,
  type StreamCallbacks,
} from "@/lib/api/chats";

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

/** Map backend message types to frontend ChatMessage[] */
function rawToMessages(raw: RawMessage[]): ChatMessage[] {
  return raw
    .filter((m) => m.type !== "SystemMessage")
    .map((m, i) => ({
      id: `hist-${i}`,
      role: (m.type === "HumanMessage" ? "user" : "assistant") as
        | "user"
        | "assistant",
      content: m.content,
      timestamp: new Date(),
    }));
}

export function useChat() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversation, setActiveConversationRaw] = useState<
    string | null
  >(null);

  const abortRef = useRef<AbortController | null>(null);
  const idCounter = useRef(0);
  // Guard: skip loadMessages when sendMessage just created a new chat
  const skipNextLoadRef = useRef(false);

  const genId = () => {
    idCounter.current += 1;
    return `msg-${idCounter.current}-${Date.now()}`;
  };

  // ---- Load conversation list ----

  const loadConversations = useCallback(async () => {
    try {
      const chatIds = await listChats();
      const convos: Conversation[] = await Promise.all(
        chatIds.map(async (id) => {
          try {
            const meta = await getChatMetadata(id);
            return { id, title: meta.name, updatedAt: new Date() };
          } catch {
            return {
              id,
              title: `Chat ${id.slice(0, 8)}`,
              updatedAt: new Date(),
            };
          }
        }),
      );
      setConversations(convos);
    } catch (err) {
      console.error("Failed to load conversations:", err);
    }
  }, []);

  // ---- Load messages for a conversation ----

  const loadMessages = useCallback(async (chatId: string) => {
    try {
      const raw = await getChatMessages(chatId);
      setMessages(rawToMessages(raw));
    } catch (err) {
      console.error("Failed to load messages:", err);
      setMessages([]);
    }
  }, []);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  // Load messages when active conversation changes
  useEffect(() => {
    if (activeConversation) {
      if (skipNextLoadRef.current) {
        skipNextLoadRef.current = false;
        return;
      }
      loadMessages(activeConversation);
    }
  }, [activeConversation, loadMessages]);

  // ---- Select a conversation ----

  const selectConversation = useCallback(
    (id: string) => {
      if (id === activeConversation) return;
      // Cancel any ongoing stream
      if (abortRef.current) {
        abortRef.current.abort();
        abortRef.current = null;
      }
      setIsLoading(false);
      setActiveConversationRaw(id);
    },
    [activeConversation],
  );

  // ---- New chat (clear state) ----

  const newChat = useCallback(() => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    setActiveConversationRaw(null);
    setMessages([]);
    setIsLoading(false);
  }, []);

  // ---- Send a message with SSE streaming ----

  const sendMessage = useCallback(
    async (text: string) => {
      let chatId = activeConversation;

      // Create a new chat if none is active
      if (!chatId) {
        try {
          const result = await createChat();
          chatId = result.chat_id;
          skipNextLoadRef.current = true;
          setActiveConversationRaw(chatId);
          setConversations((prev) => [
            {
              id: chatId!,
              title: text.slice(0, 40),
              updatedAt: new Date(),
            },
            ...prev,
          ]);
        } catch (err) {
          console.error("Failed to create chat:", err);
          return;
        }
      }

      // Add user message
      const userMsg: ChatMessage = {
        id: genId(),
        role: "user",
        content: text,
        timestamp: new Date(),
      };
      setMessages((prev) => [...prev, userMsg]);
      setIsLoading(true);

      // Add assistant placeholder for streaming
      const assistantId = genId();
      setMessages((prev) => [
        ...prev,
        {
          id: assistantId,
          role: "assistant",
          content: "",
          timestamp: new Date(),
        },
      ]);

      const callbacks: StreamCallbacks = {
        onToken: (token) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId ? { ...m, content: m.content + token } : m,
            ),
          );
        },
        onNodeStart: (node) => {
          console.debug("Agent node started:", node);
        },
        onStopped: (message) => {
          console.debug("Generation stopped:", message);
        },
        onError: (message) => {
          setMessages((prev) =>
            prev.map((m) =>
              m.id === assistantId
                ? { ...m, content: m.content || `Error: ${message}` }
                : m,
            ),
          );
        },
        onDone: () => {
          setIsLoading(false);
          abortRef.current = null;
          // Refresh conversation list (backend may have updated the title)
          loadConversations();
        },
      };

      abortRef.current = streamCompletion(chatId, text, callbacks);
    },
    [activeConversation, loadConversations],
  );

  // ---- Stop generation ----

  const stopCurrentGeneration = useCallback(async () => {
    if (abortRef.current) {
      abortRef.current.abort();
      abortRef.current = null;
    }
    if (activeConversation) {
      try {
        await stopGeneration(activeConversation);
      } catch {
        // best-effort
      }
    }
    setIsLoading(false);
  }, [activeConversation]);

  // ---- Delete a conversation ----

  const deleteConversation = useCallback(
    async (id: string) => {
      try {
        await deleteChat(id);
        setConversations((prev) => prev.filter((c) => c.id !== id));
        if (activeConversation === id) {
          setActiveConversationRaw(null);
          setMessages([]);
        }
      } catch (err) {
        console.error("Failed to delete chat:", err);
      }
    },
    [activeConversation],
  );

  return {
    messages,
    isLoading,
    conversations,
    activeConversation,
    setActiveConversation: selectConversation,
    sendMessage,
    stopGeneration: stopCurrentGeneration,
    newChat,
    deleteConversation,
    // Backward-compatible aliases (used by ChatPage)
    clearMessages: newChat,
    // Stubs for template/preview features (removed — was mock-only)
    previewHtml: "",
    selectTemplate: (_id: string) => {},
    setPreviewHtml: (_html: string) => {},
  };
}
