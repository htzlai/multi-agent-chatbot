import { Plus, MessageSquare } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { cn } from "@/lib/utils";
import type { Conversation } from "@/hooks/use-chat";

interface ChatSidebarProps {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onNew: () => void;
}

function timeAgo(date: Date): string {
  const diff = Date.now() - date.getTime();
  const mins = Math.floor(diff / 60000);
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.floor(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.floor(hrs / 24);
  return `${days}d ago`;
}

export default function ChatSidebar({
  conversations,
  activeId,
  onSelect,
  onNew,
}: ChatSidebarProps) {
  return (
    <div className="flex h-full flex-col border-r border-border bg-surface">
      <div className="border-b border-border p-3">
        <Button
          variant="outline"
          size="sm"
          className="w-full justify-start gap-2"
          onClick={onNew}
        >
          <Plus className="h-4 w-4" />
          New Chat
        </Button>
      </div>

      <ScrollArea className="flex-1">
        <div className="space-y-0.5 p-2">
          {conversations.map((c) => (
            <button
              key={c.id}
              onClick={() => onSelect(c.id)}
              className={cn(
                "flex w-full items-start gap-2 rounded-lg px-3 py-2.5 text-left transition-colors hover:bg-accent",
                activeId === c.id && "bg-accent"
              )}
            >
              <MessageSquare className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-medium text-foreground">
                  {c.title}
                </p>
                <p className="text-xs text-muted-foreground">{timeAgo(c.updatedAt)}</p>
              </div>
            </button>
          ))}
        </div>
      </ScrollArea>
    </div>
  );
}
