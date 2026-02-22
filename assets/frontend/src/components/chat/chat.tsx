"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: Date;
}

interface ChatProps {
  messages: Message[];
  isStreaming?: boolean;
  currentStreamingContent?: string;
  className?: string;
}

export function Chat({
  messages,
  isStreaming = false,
  currentStreamingContent = "",
  className,
}: ChatProps) {
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = React.useState(true);

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStreamingContent]);

  const handleScroll = React.useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    setIsNearBottom(distanceFromBottom < 100);
  }, []);

  return (
    <div className={cn("flex flex-1 flex-col overflow-hidden", className)}>
      {/* Messages Container */}
      <ScrollArea
        ref={containerRef}
        className="flex-1"
        onScroll={handleScroll}
      >
        <div className="mx-auto flex min-h-0 max-w-4xl flex-col gap-4 px-4 py-6">
          {/* Welcome Message (empty state) */}
          {messages.length === 0 && !isStreaming && (
            <div className="flex flex-col items-center justify-center py-20 text-center">
              <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-primary/10">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="32"
                  height="32"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="text-primary"
                >
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <h2 className="mb-2 text-xl font-semibold">How can I help you today?</h2>
              <p className="max-w-md text-sm text-muted-foreground">
                I can help you search through your documents, answer questions, and more.
                Just type a message below to get started.
              </p>
            </div>
          )}

          {/* Messages */}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}

          {/* Streaming Content */}
          {isStreaming && currentStreamingContent && (
            <MessageBubble
              message={{
                id: "streaming",
                role: "assistant",
                content: currentStreamingContent,
              }}
              isStreaming
            />
          )}

          {/* Thinking indicator */}
          {isStreaming && !currentStreamingContent && (
            <div className="flex items-start gap-3">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-background ring-1 ring-border">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  width="14"
                  height="14"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="animate-pulse"
                >
                  <path d="M12 2L2 7l10 5 10-5-10-5z" />
                  <path d="M2 17l10 5 10-5" />
                  <path d="M2 12l10 5 10-5" />
                </svg>
              </div>
              <div className="flex items-center gap-1 text-muted-foreground">
                <span className="animate-bounce-dot" style={{ animationDelay: "0ms" }}>
                  .
                </span>
                <span className="animate-bounce-dot" style={{ animationDelay: "150ms" }}>
                  .
                </span>
                <span className="animate-bounce-dot" style={{ animationDelay: "300ms" }}>
                  .
                </span>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} className="h-4 shrink-0" />
        </div>
      </ScrollArea>

      {/* Scroll to bottom button */}
      {!isNearBottom && messages.length > 0 && (
        <div className="absolute bottom-24 left-1/2 -translate-x-1/2">
          <Button
            variant="secondary"
            size="sm"
            className="shadow-lg"
            onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })}
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              width="16"
              height="16"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="m6 9 6 6 6-6" />
            </svg>
          </Button>
        </div>
      )}
    </div>
  );
}

interface MessageBubbleProps {
  message: Message;
}

function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "group/message flex w-full items-start gap-3 fade-in animate-fade-in",
        isUser && "justify-end"
      )}
      data-role={message.role}
    >
      {/* AI Avatar */}
      {!isUser && (
        <div className="-mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-background ring-1 ring-border">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2L2 7l10 5 10-5-10-5z" />
            <path d="M2 17l10 5 10-5" />
            <path d="M2 12l10 5 10-5" />
          </svg>
        </div>
      )}

      {/* Message Content */}
      <div
        className={cn(
          "flex max-w-[calc(100%-3rem)] flex-col gap-2",
          isUser && "items-end"
        )}
      >
        {/* User message bubble */}
        {isUser ? (
          <div
            className="break-words rounded-2xl px-4 py-2 text-white"
            style={{ backgroundColor: "#006cff" }}
          >
            <MarkdownContent content={message.content} />
          </div>
        ) : (
          /* AI message */
          <div className="text-left">
            <MarkdownContent content={message.content} />
          </div>
        )}
      </div>
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
  // Simple markdown rendering - in production use react-markdown
  const renderContent = () => {
    const lines = content.split("\n");
    return lines.map((line, i) => {
      // Code block
      if (line.startsWith("```")) {
        return null;
      }
      // Headers
      if (line.startsWith("### ")) {
        return (
          <h3 key={i} className="mb-2 mt-4 font-semibold">
            {line.replace("### ", "")}
          </h3>
        );
      }
      if (line.startsWith("## ")) {
        return (
          <h2 key={i} className="mb-2 mt-4 text-lg font-semibold">
            {line.replace("## ", "")}
          </h2>
        );
      }
      if (line.startsWith("# ")) {
        return (
          <h1 key={i} className="mb-2 mt-4 text-xl font-bold">
            {line.replace("# ", "")}
          </h1>
        );
      }
      // List items
      if (line.match(/^[-*]\s/)) {
        return (
          <li key={i} className="ml-4 list-disc">
            {renderInlineContent(line.replace(/^[-*]\s/, ""))}
          </li>
        );
      }
      // Numbered list
      if (line.match(/^\d+\.\s/)) {
        return (
          <li key={i} className="ml-4 list-decimal">
            {renderInlineContent(line.replace(/^\d+\.\s/, ""))}
          </li>
        );
      }
      // Empty line
      if (!line.trim()) {
        return <br key={i} />;
      }
      // Regular paragraph
      return (
        <p key={i} className="mb-2 last:mb-0">
          {renderInlineContent(line)}
        </p>
      );
    });
  };

  return <div className="text-sm">{renderContent()}</div>;
}

function renderInlineContent(text: string) {
  // Handle inline code and basic formatting
  const parts = text.split(/(`[^`]+`|\*\*[^*]+\*\*|[^*]+)/g);
  return parts.map((part, i) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code
          key={i}
          className="rounded bg-muted px-1 py-0.5 font-mono text-xs"
        >
          {part.slice(1, -1)}
        </code>
      );
    }
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    return part;
  });
}
