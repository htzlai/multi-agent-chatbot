import { motion } from "framer-motion";
import { User, Sparkles } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import CodeBlock from "./CodeBlock";
import type { ChatMessage as ChatMessageType } from "@/hooks/use-chat";

interface ChatMessageProps {
  message: ChatMessageType;
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const isUser = message.role === "user";

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
      className={`flex gap-3 ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* Avatar */}
      <Avatar className="h-7 w-7 shrink-0">
        <AvatarFallback
          className={
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-muted text-foreground"
          }
        >
          {isUser ? (
            <User className="h-3.5 w-3.5" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
        </AvatarFallback>
      </Avatar>

      {/* Bubble */}
      <div
        className={`max-w-[85%] rounded-xl px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "bg-primary text-primary-foreground"
            : "bg-muted text-foreground"
        }`}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>

        {/* Code blocks */}
        {message.codeBlocks?.map((block, idx) => (
          <CodeBlock key={idx} language={block.language} code={block.code} />
        ))}

        {/* Timestamp */}
        <p
          className={`mt-2 text-[10px] ${
            isUser
              ? "text-primary-foreground/60"
              : "text-muted-foreground"
          }`}
        >
          {message.timestamp.toLocaleTimeString([], {
            hour: "2-digit",
            minute: "2-digit",
          })}
        </p>
      </div>
    </motion.div>
  );
}
