import { useState, useRef, useEffect } from "react";
import { ArrowUp, Plus, LayoutGrid } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (text: string) => void;
  onOpenTemplates: () => void;
  disabled?: boolean;
}

export default function ChatInput({ onSend, onOpenTemplates, disabled }: ChatInputProps) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-resize
  useEffect(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = Math.min(el.scrollHeight, 160) + "px";
  }, [value]);

  const handleSend = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="border-t border-border bg-background px-3 pb-3 pt-2">
      <div className="rounded-xl border border-border bg-background shadow-card">
        <textarea
          ref={textareaRef}
          value={value}
          onChange={(e) => setValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Describe what you want to build..."
          rows={1}
          disabled={disabled}
          className="w-full resize-none bg-transparent px-4 py-3 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none disabled:opacity-50"
        />
        <div className="flex items-center justify-between px-2 pb-2">
          <div className="flex items-center gap-0.5">
            <Button variant="ghost" size="icon-sm" className="text-muted-foreground" disabled={disabled}>
              <Plus className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 text-xs text-muted-foreground"
              onClick={onOpenTemplates}
              disabled={disabled}
            >
              <LayoutGrid className="h-3.5 w-3.5" />
              Templates
            </Button>
          </div>
          <Button
            size="icon-sm"
            className="rounded-lg"
            onClick={handleSend}
            disabled={disabled || !value.trim()}
          >
            <ArrowUp className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
