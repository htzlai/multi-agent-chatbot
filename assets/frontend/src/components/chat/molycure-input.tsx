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
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KEY, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
*/
"use client";

import * as React from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { PaperclipIcon, ArrowUpIcon, StopIcon } from "./icons-moly";

interface MolycureInputProps {
  onSendMessage?: (content: string) => void;
  onStopStreaming?: () => void;
  isStreaming?: boolean;
  disabled?: boolean;
  placeholder?: string;
  className?: string;
}

export function MolycureInput({
  onSendMessage,
  onStopStreaming,
  isStreaming = false,
  disabled = false,
  placeholder = "Send a message...",
  className,
}: MolycureInputProps) {
  const [input, setInput] = React.useState("");
  const textareaRef = React.useRef<HTMLTextAreaElement>(null);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming || disabled) return;
    onSendMessage?.(input.trim());
    setInput("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // Auto-resize textarea - molysmol style
  React.useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "44px";
      const scrollHeight = textareaRef.current.scrollHeight;
      textareaRef.current.style.height = `${Math.min(scrollHeight, 200)}px`;
    }
  }, [input]);

  // Focus on mount
  React.useEffect(() => {
    const timer = setTimeout(() => {
      textareaRef.current?.focus();
    }, 100);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className={cn("relative flex w-full flex-col gap-4", className)}>
      <form
        onSubmit={handleSubmit}
        className="rounded-xl border border-border bg-background p-3 shadow-xs transition-all duration-200 focus-within:border-border hover:border-muted-foreground/50"
      >
        {/* Hidden file input */}
        <input
          className="pointer-events-none fixed -top-4 -left-4 size-0.5 opacity-0"
          multiple
          onChange={() => {}}
          ref={fileInputRef}
          tabIndex={-1}
          type="file"
        />

        {/* Textarea - molysmol style */}
        <div className="flex flex-row items-start gap-1 sm:gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={placeholder}
            disabled={disabled}
            rows={1}
            className="grow resize-none border-0! border-none! bg-transparent p-2 text-base outline-none ring-0 [-ms-overflow-style:none] [scrollbar-width:none] placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 [&::-webkit-scrollbar]:hidden"
            style={{ minHeight: "44px", maxHeight: "200px" }}
          />
        </div>

        {/* Toolbar - molysmol style */}
        <div className="border-top-0! border-t-0! flex items-center justify-between border-t p-0 shadow-none dark:border-0 dark:border-transparent!">
          <div className="flex items-center gap-0 sm:gap-0.5">
            {/* Attachment button */}
            <Button
              type="button"
              className="aspect-square h-8 rounded-lg p-1 transition-colors hover:bg-accent"
              disabled={disabled || isStreaming}
              variant="ghost"
              onClick={() => fileInputRef.current?.click()}
            >
              <PaperclipIcon size={14} />
            </Button>
          </div>

          {/* Submit or Stop button - molysmol style */}
          {isStreaming ? (
            <Button
              type="button"
              className="size-7 rounded-full bg-foreground p-1 text-background transition-colors duration-200 hover:bg-foreground/90 disabled:bg-muted disabled:text-muted-foreground"
              onClick={onStopStreaming}
            >
              <StopIcon size={14} />
            </Button>
          ) : (
            <Button
              type="submit"
              className="size-8 rounded-full bg-primary text-primary-foreground transition-colors duration-200 hover:bg-primary/90 disabled:bg-muted disabled:text-muted-foreground"
              disabled={!input.trim() || disabled}
            >
              <ArrowUpIcon size={14} />
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
