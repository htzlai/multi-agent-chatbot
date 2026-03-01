import { useState } from "react";
import { useLocation } from "react-router-dom";
import { PanelLeftClose, PanelLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from "@/components/ui/resizable";
import { useIsMobile } from "@/hooks/use-mobile";
import { useChat } from "@/hooks/use-chat";
import Navbar from "@/components/layout/Navbar";
import ChatSidebar from "@/components/chat/ChatSidebar";
import ChatPanel from "@/components/chat/ChatPanel";
import PreviewPanel from "@/components/chat/PreviewPanel";
import TemplateSelector from "@/components/chat/TemplateSelector";
import { cn } from "@/lib/utils";
import { useEffect } from "react";

export default function ChatPage() {
  const isMobile = useIsMobile();
  const location = useLocation();
  const initialPrompt = (location.state as { initialPrompt?: string } | null)?.initialPrompt;

  const {
    messages,
    isLoading,
    previewHtml,
    conversations,
    activeConversation,
    setActiveConversation,
    sendMessage,
    selectTemplate,
    clearMessages,
  } = useChat();

  const [sidebarOpen, setSidebarOpen] = useState(!isMobile);
  const [templateOpen, setTemplateOpen] = useState(false);
  const [mobileTab, setMobileTab] = useState<"chat" | "preview">("chat");

  // Handle initial prompt from landing page
  useEffect(() => {
    if (initialPrompt?.trim()) {
      sendMessage(initialPrompt.trim());
      // Clear the state so it doesn't re-send on re-renders
      window.history.replaceState({}, "");
    }
    // Only run once on mount
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-background">
      {/* Compact navbar */}
      <Navbar compact />

      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar toggle (desktop) */}
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
                onNew={clearMessages}
              />
            )}
          </div>
        )}

        <div className="flex flex-1 flex-col overflow-hidden">
          {/* Sidebar toggle button + mobile tabs */}
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

            {isMobile && (
              <div className="flex gap-1">
                {(["chat", "preview"] as const).map((tab) => (
                  <Button
                    key={tab}
                    variant={mobileTab === tab ? "secondary" : "ghost"}
                    size="sm"
                    className="h-7 text-xs capitalize"
                    onClick={() => setMobileTab(tab)}
                  >
                    {tab}
                  </Button>
                ))}
              </div>
            )}
          </div>

          {/* Main content */}
          {isMobile ? (
            /* Mobile: tabbed */
            <div className="flex-1 overflow-hidden">
              {mobileTab === "chat" ? (
                <ChatPanel
                  messages={messages}
                  isLoading={isLoading}
                  onSend={sendMessage}
                  onOpenTemplates={() => setTemplateOpen(true)}
                />
              ) : (
                <PreviewPanel previewHtml={previewHtml} />
              )}
            </div>
          ) : (
            /* Desktop: resizable split */
            <ResizablePanelGroup direction="horizontal">
              <ResizablePanel defaultSize={40} minSize={28} maxSize={60}>
                <ChatPanel
                  messages={messages}
                  isLoading={isLoading}
                  onSend={sendMessage}
                  onOpenTemplates={() => setTemplateOpen(true)}
                />
              </ResizablePanel>
              <ResizableHandle withHandle />
              <ResizablePanel defaultSize={60} minSize={30}>
                <PreviewPanel previewHtml={previewHtml} />
              </ResizablePanel>
            </ResizablePanelGroup>
          )}
        </div>
      </div>

      {/* Template selector */}
      <TemplateSelector
        open={templateOpen}
        onClose={() => setTemplateOpen(false)}
        onSelect={selectTemplate}
      />
    </div>
  );
}
