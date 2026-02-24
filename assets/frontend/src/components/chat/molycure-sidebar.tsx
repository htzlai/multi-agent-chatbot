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
import Link from "next/link";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { PlusIcon, MessageIcon, HomeIcon, TrashIcon, ChevronLeftIcon } from "./icons-moly";

interface ChatHistoryItem {
  id: string;
  name: string;
  timestamp?: string;
}

interface MolycureSidebarProps {
  className?: string;
  chatHistory?: ChatHistoryItem[];
  currentChatId?: string | null;
  onNewChat?: () => void;
  onSelectChat?: (chatId: string) => void;
  onDeleteChat?: (chatId: string) => void;
}

// Date grouping - molysmol style
function groupChatsByDate(chats: ChatHistoryItem[]) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today.getTime() - 24 * 60 * 60 * 1000);
  const lastWeek = new Date(today.getTime() - 7 * 24 * 60 * 60 * 1000);
  const lastMonth = new Date(today.getTime() - 30 * 24 * 60 * 60 * 1000);

  return chats.reduce(
    (groups, chat) => {
      const chatDate = chat.timestamp ? new Date(chat.timestamp) : now;
      const chatDay = new Date(chatDate.getFullYear(), chatDate.getMonth(), chatDate.getDate());

      if (chatDay.getTime() === today.getTime()) {
        groups.today.push(chat);
      } else if (chatDay.getTime() === yesterday.getTime()) {
        groups.yesterday.push(chat);
      } else if (chatDay >= lastWeek) {
        groups.lastWeek.push(chat);
      } else if (chatDay >= lastMonth) {
        groups.lastMonth.push(chat);
      } else {
        groups.older.push(chat);
      }

      return groups;
    },
    {
      today: [] as ChatHistoryItem[],
      yesterday: [] as ChatHistoryItem[],
      lastWeek: [] as ChatHistoryItem[],
      lastMonth: [] as ChatHistoryItem[],
      older: [] as ChatHistoryItem[],
    }
  );
}

export function MolycureSidebar({
  className,
  chatHistory = [],
  currentChatId,
  onNewChat,
  onSelectChat,
  onDeleteChat,
}: MolycureSidebarProps) {
  const [isCollapsed, setIsCollapsed] = React.useState(false);

  const groupedChats = groupChatsByDate(chatHistory);

  return (
    <aside
      className={cn(
        "flex h-full flex-col border-r bg-sidebar transition-all duration-200",
        isCollapsed ? "w-[60px]" : "w-[280px]",
        className
      )}
    >
      {/* Header */}
      <div className="flex h-14 items-center justify-between border-b border-sidebar-border px-4">
        {!isCollapsed && (
          <Link href="/chat" className="flex items-center gap-2">
            <span className="font-semibold text-sidebar-foreground">Spark Chat</span>
          </Link>
        )}
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-8 text-sidebar-foreground/70 hover:text-sidebar-foreground"
          onClick={() => setIsCollapsed(!isCollapsed)}
        >
          <ChevronLeftIcon
            className={cn("transition-transform h-4 w-4", isCollapsed && "rotate-180")}
          />
        </Button>
      </div>

      {/* New Chat Button - molysmol style */}
      <div className="p-3">
        <Button
          onClick={onNewChat}
          className={cn(
            "w-full justify-start gap-2 bg-sidebar-primary text-sidebar-primary-foreground hover:bg-sidebar-primary/90",
            isCollapsed && "px-2 justify-center"
          )}
        >
          <PlusIcon size={18} />
          {!isCollapsed && <span>New Chat</span>}
        </Button>
      </div>

      {/* Chat History - molysmol style */}
      <ScrollArea className="flex-1 px-3">
        <div className="space-y-4 pb-4">
          {/* Today's chats */}
          {groupedChats.today.length > 0 && !isCollapsed && (
            <div>
              <h3 className="mb-2 px-2 text-xs font-medium text-sidebar-foreground/70">
                Today
              </h3>
              {groupedChats.today.map((chat) => (
                <ChatItem
                  key={chat.id}
                  chat={chat}
                  isActive={currentChatId === chat.id}
                  onSelect={() => onSelectChat?.(chat.id)}
                  onDelete={() => onDeleteChat?.(chat.id)}
                />
              ))}
            </div>
          )}

          {/* Yesterday's chats */}
          {groupedChats.yesterday.length > 0 && !isCollapsed && (
            <div>
              <h3 className="mb-2 px-2 text-xs font-medium text-sidebar-foreground/70">
                Yesterday
              </h3>
              {groupedChats.yesterday.map((chat) => (
                <ChatItem
                  key={chat.id}
                  chat={chat}
                  isActive={currentChatId === chat.id}
                  onSelect={() => onSelectChat?.(chat.id)}
                  onDelete={() => onDeleteChat?.(chat.id)}
                />
              ))}
            </div>
          )}

          {/* Last week's chats */}
          {groupedChats.lastWeek.length > 0 && !isCollapsed && (
            <div>
              <h3 className="mb-2 px-2 text-xs font-medium text-sidebar-foreground/70">
                Last 7 days
              </h3>
              {groupedChats.lastWeek.map((chat) => (
                <ChatItem
                  key={chat.id}
                  chat={chat}
                  isActive={currentChatId === chat.id}
                  onSelect={() => onSelectChat?.(chat.id)}
                  onDelete={() => onDeleteChat?.(chat.id)}
                />
              ))}
            </div>
          )}

          {/* Last month's chats */}
          {groupedChats.lastMonth.length > 0 && !isCollapsed && (
            <div>
              <h3 className="mb-2 px-2 text-xs font-medium text-sidebar-foreground/70">
                Last 30 days
              </h3>
              {groupedChats.lastMonth.map((chat) => (
                <ChatItem
                  key={chat.id}
                  chat={chat}
                  isActive={currentChatId === chat.id}
                  onSelect={() => onSelectChat?.(chat.id)}
                  onDelete={() => onDeleteChat?.(chat.id)}
                />
              ))}
            </div>
          )}

          {/* Older chats */}
          {groupedChats.older.length > 0 && !isCollapsed && (
            <div>
              <h3 className="mb-2 px-2 text-xs font-medium text-sidebar-foreground/70">
                Older
              </h3>
              {groupedChats.older.map((chat) => (
                <ChatItem
                  key={chat.id}
                  chat={chat}
                  isActive={currentChatId === chat.id}
                  onSelect={() => onSelectChat?.(chat.id)}
                  onDelete={() => onDeleteChat?.(chat.id)}
                />
              ))}
            </div>
          )}

          {/* Empty state - molysmol style */}
          {chatHistory.length === 0 && !isCollapsed && (
            <p className="px-2 py-4 text-center text-sm text-sidebar-foreground/50">
              Your conversations will appear here once you start chatting!
            </p>
          )}
        </div>
      </ScrollArea>

      {/* Footer */}
      <div className="border-t border-sidebar-border p-3">
        <Link
          href="/"
          className={cn(
            "flex items-center gap-2 rounded-md px-2 py-2 text-sm text-sidebar-foreground/70 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
            isCollapsed && "justify-center"
          )}
        >
          <HomeIcon size={18} />
          {!isCollapsed && <span>Home</span>}
        </Link>
      </div>
    </aside>
  );
}

interface ChatItemProps {
  chat: ChatHistoryItem;
  isActive?: boolean;
  onSelect?: () => void;
  onDelete?: () => void;
}

function ChatItem({ chat, isActive, onSelect, onDelete }: ChatItemProps) {
  return (
    <div
      className={cn(
        "group flex cursor-pointer items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        isActive && "bg-sidebar-accent text-sidebar-accent-foreground"
      )}
      onClick={onSelect}
    >
      <MessageIcon size={16} className="shrink-0 text-sidebar-foreground/70" />
      <span className="flex-1 truncate">{chat.name}</span>
      <button
        onClick={(e) => {
          e.stopPropagation();
          onDelete?.();
        }}
        className="opacity-0 transition-opacity hover:text-destructive group-hover:opacity-100"
      >
        <TrashIcon size={14} />
      </button>
    </div>
  );
}
