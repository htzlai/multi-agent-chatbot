import { useRef, useEffect } from "react";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Sparkles, MessageSquare, LayoutDashboard, FileText, ShoppingBag } from "lucide-react";
import ChatMessage from "./ChatMessage";
import ChatInput from "./ChatInput";
import type { ChatMessage as ChatMessageType } from "@/hooks/use-chat";

interface ChatPanelProps {
  messages: ChatMessageType[];
  isLoading: boolean;
  onSend: (text: string) => void;
  onOpenTemplates: () => void;
}

const suggestions = [
  { text: "Build a dashboard with charts", icon: LayoutDashboard },
  { text: "Create a modern blog", icon: FileText },
  { text: "Design an e-commerce store", icon: ShoppingBag },
];

export default function ChatPanel({
  messages,
  isLoading,
  onSend,
  onOpenTemplates,
}: ChatPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  const isEmpty = messages.length === 0;

  return (
    <div className="flex h-full flex-col">
      <ScrollArea className="flex-1">
        <div className="p-4">
          {isEmpty ? (
            /* Empty state */
            <div className="flex h-full min-h-[60vh] flex-col items-center justify-center">
              <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-muted">
                <Sparkles className="h-6 w-6 text-foreground" />
              </div>
              <h3 className="mt-4 text-lg font-semibold text-foreground">
                What do you want to build?
              </h3>
              <p className="mt-1 text-center text-sm text-muted-foreground">
                Describe your idea or pick a suggestion below.
              </p>

              <div className="mt-6 flex flex-col gap-2">
                {suggestions.map((s) => (
                  <button
                    key={s.text}
                    onClick={() => onSend(s.text)}
                    className="flex items-center gap-3 rounded-xl border border-border bg-background px-4 py-3 text-left text-sm text-foreground transition-colors hover:bg-muted"
                  >
                    <s.icon className="h-4 w-4 text-muted-foreground" />
                    {s.text}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            /* Messages */
            <div className="space-y-4">
              {messages.map((msg) => (
                <ChatMessage key={msg.id} message={msg} />
              ))}

              {/* Loading indicator */}
              {isLoading && (
                <div className="flex items-start gap-3">
                  <div className="flex h-7 w-7 items-center justify-center rounded-full bg-muted">
                    <MessageSquare className="h-3.5 w-3.5 text-foreground" />
                  </div>
                  <div className="rounded-xl bg-muted px-4 py-3">
                    <div className="flex gap-1">
                      <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
                      <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
                      <span className="typing-dot h-2 w-2 rounded-full bg-muted-foreground" />
                    </div>
                  </div>
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </div>
      </ScrollArea>

      <ChatInput onSend={onSend} onOpenTemplates={onOpenTemplates} disabled={isLoading} />
    </div>
  );
}
