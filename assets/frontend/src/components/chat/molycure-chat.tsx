/*
# SPDX-FileCopyrightText: Copyright (c) 1993-2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
*/
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { SparklesIcon, ArrowDownIcon } from "./icons-moly";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp?: Date;
  reasoning?: string;
}

interface ChatProps {
  messages: Message[];
  isStreaming?: boolean;
  currentStreamingContent?: string;
  className?: string;
  onSendMessage?: (content: string) => void;
}

// Suggested actions - molysmol style
const suggestedActions = [
  { label: "What are the advantages of using Next.js?", icon: "💻" },
  { label: "Write code to demonstrate Dijkstra's algorithm", icon: "🔍" },
  { label: "Help me write an essay about Silicon Valley", icon: "📝" },
  { label: "What is the weather in San Francisco?", icon: "🌤️" },
];

// Greeting component - molysmol style
function Greeting() {
  return (
    <div className="mx-auto mt-4 flex size-full max-w-3xl flex-col justify-center px-4 md:mt-16 md:px-8">
      <div className="font-semibold text-xl md:text-2xl animate-fade-in" style={{ animationDelay: "0.1s" }}>
        Hello there!
      </div>
      <div className="text-xl text-muted-foreground md:text-2xl animate-fade-in" style={{ animationDelay: "0.2s" }}>
        How can I help you today?
      </div>
    </div>
  );
}

export function MolycureChat({
  messages,
  isStreaming = false,
  currentStreamingContent = "",
  className,
  onSendMessage,
}: ChatProps) {
  const messagesEndRef = React.useRef<HTMLDivElement>(null);
  const containerRef = React.useRef<HTMLDivElement>(null);
  const [isNearBottom, setIsNearBottom] = React.useState(true);

  React.useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, currentStreamingContent, isStreaming]);

  const handleScroll = React.useCallback(() => {
    if (!containerRef.current) return;
    const { scrollTop, scrollHeight, clientHeight } = containerRef.current;
    const distanceFromBottom = scrollHeight - scrollTop - clientHeight;
    setIsNearBottom(distanceFromBottom < 100);
  }, []);

  return (
    <div className={cn("flex flex-1 flex-col overflow-hidden", className)}>
      <ScrollArea
        ref={containerRef}
        className="flex-1"
        onScroll={handleScroll}
      >
        <div className="mx-auto flex min-h-0 max-w-4xl flex-col gap-4 px-2 py-4 md:gap-6 md:px-4">
          {/* Greeting - molysmol style */}
          {messages.length === 0 && !isStreaming && <Greeting />}

          {/* Messages - molysmol style */}
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

          {/* Thinking indicator - molysmol style with SparklesIcon */}
          {isStreaming && !currentStreamingContent && (
            <div className="group/message fade-in w-full animate-in duration-300" data-role="assistant">
              <div className="flex items-start justify-start gap-3">
                <div className="-mt-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-background ring-1 ring-border">
                  <div className="animate-pulse">
                    <SparklesIcon size={14} />
                  </div>
                </div>
                <div className="flex w-full flex-col gap-2 md:gap-4">
                  <div className="flex items-center gap-1 p-0 text-muted-foreground text-sm">
                    <span className="animate-pulse">Thinking</span>
                    <span className="inline-flex">
                      <span className="animate-bounce [animation-delay:0ms]">.</span>
                      <span className="animate-bounce [animation-delay:150ms]">.</span>
                      <span className="animate-bounce [animation-delay:300ms]">.</span>
                    </span>
                  </div>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} className="min-h-[24px] min-w-[24px] shrink-0" />
        </div>
      </ScrollArea>

      {/* Scroll to bottom button - molysmol style */}
      {!isNearBottom && messages.length > 0 && (
        <button
          aria-label="Scroll to bottom"
          className={`absolute bottom-4 left-1/2 z-10 -translate-x-1/2 rounded-full border bg-background p-2 shadow-lg transition-all hover:bg-muted ${
            isNearBottom
              ? "pointer-events-none scale-0 opacity-0"
              : "pointer-events-auto scale-100 opacity-100"
          }`}
          onClick={() => messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })}
          type="button"
        >
          <ArrowDownIcon className="size-4" />
        </button>
      )}

      {/* Suggested actions - molysmol style */}
      {messages.length === 0 && !isStreaming && (
        <div className="mx-auto mt-4 flex w-full max-w-3xl flex-wrap justify-center gap-2 px-4">
          {suggestedActions.map((action) => (
            <button
              key={action.label}
              onClick={() => onSendMessage?.(action.label)}
              className="flex items-center gap-2 rounded-full border border-border bg-background px-5 py-2.5 text-left text-sm font-normal text-foreground shadow-sm transition-all hover:border-primary/50 hover:bg-secondary/50 hover:shadow-md"
            >
              <span>{action.icon}</span>
              <span>{action.label}</span>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

interface MessageBubbleProps {
  message: Message;
  isStreaming?: boolean;
}

function MessageBubble({ message, isStreaming }: MessageBubbleProps) {
  const isUser = message.role === "user";

  return (
    <div
      className={cn(
        "group/message fade-in w-full animate-in duration-200",
        isUser ? "justify-end" : "justify-start"
      )}
      data-role={message.role}
    >
      <div className={cn("flex w-full items-start gap-2 md:gap-3", {
        "justify-end": isUser,
        "justify-start": !isUser,
      })}>
        {/* AI Avatar - molysmol style with ring */}
        {!isUser && (
          <div className="-mt-1 flex size-8 shrink-0 items-center justify-center rounded-full bg-background ring-1 ring-border">
            <SparklesIcon size={14} />
          </div>
        )}

        <div className={cn("flex flex-col", {
          "w-full": !isUser || isStreaming,
          "max-w-[calc(100%-2.5rem)] sm:max-w-[min(fit-content,80%)]": isUser && !isStreaming,
        })}>
          {/* Reasoning - molysmol style */}
          {message.reasoning && (
            <div className="mb-2 rounded-lg bg-muted/50 p-3 text-sm text-muted-foreground">
              <div className="mb-1 text-xs font-medium uppercase tracking-wide">Reasoning</div>
              {message.reasoning}
            </div>
          )}

          {/* User message bubble - molysmol style */}
          {isUser ? (
            <div
              className="wrap-break-word w-fit rounded-2xl px-4 py-2.5 text-[15px] text-white"
              style={{ backgroundColor: "#006cff" }}
            >
              <MarkdownContent content={message.content} />
            </div>
          ) : (
            /* AI message - molysmol style */
            <div className="text-left">
              <MarkdownContent content={message.content} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MarkdownContent({ content }: { content: string }) {
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
