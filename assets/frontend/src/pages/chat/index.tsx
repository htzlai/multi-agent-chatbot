import { useState } from "react";
import { useLocation } from "react-router-dom";
import { PanelLeftClose, PanelLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useIsMobile } from "@/hooks/use-mobile";
import { useChat } from "@/hooks/use-chat";
import Navbar from "@/components/layout/Navbar";
import ChatSidebar from "@/components/chat/ChatSidebar";
import ChatPanel from "@/components/chat/ChatPanel";
import { cn } from "@/lib/utils";
import { useEffect } from "react";

export default function ChatPage() {
  const isMobile = useIsMobile();
  const location = useLocation();
  const initialPrompt = (location.state as { initialPrompt?: string } | null)?.initialPrompt;

  const {
    messages,
    isLoading,
    conversations,
    activeConversation,
    setActiveConversation,
    sendMessage,
    stopGeneration,
    newChat,
    deleteConversation,
  } = useChat();

  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);

  // Handle initial prompt from landing page
  useEffect(() => {
    if (initialPrompt?.trim()) {
      sendMessage(initialPrompt.trim());
      window.history.replaceState({}, "");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      <Navbar compact />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar (desktop) */}
        {!isMobile && (
          <div
            className={cn(
              "transition-all duration-300",
              sidebarOpen ? "w-60" : "w-0"
            )}
          >
            {sidebarOpen && (
              <ChatSidebar
                conversations={conversations}
                activeId={activeConversation}
                onSelect={setActiveConversation}
                onNew={newChat}
                onDelete={deleteConversation}
              />
            )}
          </div>
        )}

        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Sidebar toggle */}
          <div className="flex items-center gap-1 border-b border-border px-2 py-1">
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => setSidebarOpen((p) => !p)}
              className="text-muted-foreground"
            >
              {sidebarOpen ? (
                <PanelLeftClose className="h-4 w-4" />
              ) : (
                <PanelLeft className="h-4 w-4" />
              )}
            </Button>
          </div>

          {/* Chat panel (full width) */}
          <ChatPanel
            messages={messages}
            isLoading={isLoading}
            onSend={sendMessage}
            onStop={stopGeneration}
          />
        </div>
      </div>
    </div>
  );
}
