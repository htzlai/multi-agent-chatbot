"use client";

import * as React from "react";
import { Chat } from "@/components/chat/chat";
import { ChatInput } from "@/components/chat/chat-input";
import { Sidebar } from "@/components/ui/sidebar";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: Date;
}

interface ChatHistoryItem {
  id: string;
  name: string;
  timestamp?: string;
}

export default function ChatPage() {
  const [messages, setMessages] = React.useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = React.useState(false);
  const [streamingContent, setStreamingContent] = React.useState("");
  const [currentChatId, setCurrentChatId] = React.useState<string | null>(null);
  const [chatHistory, setChatHistory] = React.useState<ChatHistoryItem[]>([]);
  const wsRef = React.useRef<WebSocket | null>(null);
  const messagesEndRef = React.useRef<HTMLDivElement>(null);

  // Load initial chat ID
  React.useEffect(() => {
    const fetchCurrentChatId = async () => {
      try {
        const response = await fetch("/api/chat_id");
        if (response.ok) {
          const { chat_id } = await response.json();
          setCurrentChatId(chat_id);
        }
      } catch (error) {
        console.error("Error fetching current chat ID:", error);
      }
    };
    fetchCurrentChatId();
    fetchChatHistory();
  }, []);

  // Fetch chat history
  const fetchChatHistory = async () => {
    try {
      const response = await fetch("/api/chats");
      if (response.ok) {
        const data = await response.json();
        // Transform chat IDs to history items
        const historyItems: ChatHistoryItem[] = (data.chats || []).map((id: string, index: number) => ({
          id,
          name: `Chat ${index + 1}`,
        }));
        setChatHistory(historyItems);
      }
    } catch (error) {
      console.error("Error fetching chat history:", error);
    }
  };

  // WebSocket connection
  React.useEffect(() => {
    if (!currentChatId) return;

    const wsProtocol = "ws:";
    const wsHost = "localhost";
    const wsPort = "8000";

    const ws = new WebSocket(`${wsProtocol}//${wsHost}:${wsPort}/ws/chat/${currentChatId}`);
    wsRef.current = ws;

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const type = msg.type;
      const text = msg.data ?? msg.token ?? "";

      switch (type) {
        case "history": {
          if (Array.isArray(msg.messages)) {
            const loadedMessages: Message[] = msg.messages.map((m: { type: string; content: unknown }, index: number) => ({
              id: `${type}-${index}`,
              role: m.type === "HumanMessage" ? "user" : "assistant",
              content: typeof m.content === "string" ? m.content : String(m.content || ""),
            }));
            setMessages(loadedMessages);
            setIsStreaming(false);
          }
          break;
        }
        case "token": {
          if (!text) break;
          setStreamingContent((prev) => prev + text);
          break;
        }
        case "node_start": {
          if (msg?.data === "generate") {
            setIsStreaming(true);
            setStreamingContent("");
          }
          break;
        }
        case "node_end": {
          setIsStreaming(false);
          // Add the completed message to the list
          const content = streamingContent;
          if (content) {
            setMessages((prev) => [
              ...prev,
              {
                id: `assistant-${Date.now()}`,
                role: "assistant",
                content,
              },
            ]);
            setStreamingContent("");
          }
          break;
        }
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket error:", error);
      setIsStreaming(false);
    };

    ws.onclose = () => {
      console.log("WebSocket connection closed");
      setIsStreaming(false);
    };

    return () => {
      ws.close();
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentChatId]);

  // Scroll to bottom when messages change
  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, streamingContent, isStreaming]);

  // Handle new chat
  const handleNewChat = async () => {
    try {
      const response = await fetch("/api/chat/new", {
        method: "POST",
      });

      if (response.ok) {
        const data = await response.json();
        setCurrentChatId(data.chat_id);
        setMessages([]);
        setStreamingContent("");
        await fetchChatHistory();
      }
    } catch (error) {
      console.error("Error creating new chat:", error);
    }
  };

  // Handle select chat
  const handleSelectChat = async (chatId: string) => {
    try {
      const response = await fetch("/api/chat_id", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ chat_id: chatId }),
      });

      if (response.ok) {
        setCurrentChatId(chatId);
        setMessages([]);
        setStreamingContent("");
      }
    } catch (error) {
      console.error("Error selecting chat:", error);
    }
  };

  // Handle delete chat
  const handleDeleteChat = async (chatId: string) => {
    try {
      const response = await fetch(`/api/chat/${chatId}`, {
        method: "DELETE",
      });

      if (response.ok) {
        await fetchChatHistory();
        // If deleted current chat, switch to another
        if (currentChatId === chatId) {
          const remaining = chatHistory.filter((c) => c.id !== chatId);
          if (remaining.length > 0) {
            await handleSelectChat(remaining[0].id);
          } else {
            await handleNewChat();
          }
        }
      }
    } catch (error) {
      console.error("Error deleting chat:", error);
    }
  };

  // Handle send message
  const handleSendMessage = (content: string) => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return;

    // Add user message immediately
    setMessages((prev) => [
      ...prev,
      {
        id: `user-${Date.now()}`,
        role: "user",
        content,
      },
    ]);

    // Send via WebSocket
    wsRef.current.send(
      JSON.stringify({
        message: content,
      })
    );

    setIsStreaming(true);
    setStreamingContent("");
  };

  // Handle stop streaming
  const handleStopStreaming = () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
      setIsStreaming(false);
    }
  };

  return (
    <div className="flex h-screen w-full overflow-hidden bg-background">
      {/* Sidebar */}
      <Sidebar
        chatHistory={chatHistory}
        currentChatId={currentChatId}
        onNewChat={handleNewChat}
        onSelectChat={handleSelectChat}
        onDeleteChat={handleDeleteChat}
      />

      {/* Main Chat Area */}
      <main className="relative flex flex-1 flex-col overflow-hidden">
        {/* Messages */}
        <Chat
          messages={messages}
          isStreaming={isStreaming}
          currentStreamingContent={streamingContent}
          className="flex-1"
        />

        {/* Input Area */}
        <div className="mx-auto w-full max-w-4xl">
          <ChatInput
            onSendMessage={handleSendMessage}
            onStopStreaming={handleStopStreaming}
            isStreaming={isStreaming}
            disabled={!currentChatId}
          />
        </div>

        <div ref={messagesEndRef} />
      </main>
    </div>
  );
}
