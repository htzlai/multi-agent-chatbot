import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Plus, Sparkles, ArrowUp, Dices } from "lucide-react";
import { Button } from "@/components/ui/button";
import { motion } from "framer-motion";

export default function HeroSection() {
  const [inputValue, setInputValue] = useState("");
  const navigate = useNavigate();

  const handleStart = () => {
    navigate("/chat", { state: { initialPrompt: inputValue } });
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleStart();
    }
  };

  return (
    <section className="relative overflow-hidden bg-surface px-4 pb-20 pt-24 sm:px-6 lg:px-8">
      {/* Subtle gradient overlay */}
      <div className="pointer-events-none absolute inset-0 bg-gradient-to-b from-background to-surface" />

      <div className="relative mx-auto max-w-3xl text-center">
        {/* Headline */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="text-4xl font-extrabold tracking-tight text-foreground sm:text-5xl lg:text-6xl"
        >
          Just Press{" "}
          <span className="text-foreground">Enter</span>,
          <br />
          Ship Like a <span className="text-foreground">Pro</span>
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="mx-auto mt-4 max-w-lg text-base text-muted-foreground sm:text-lg"
        >
          Your AI Dev Agent for the Vibe Coding Era.
          <br className="hidden sm:block" />
          Orchestrate code, cloud, and collaboration to ship real products.
        </motion.p>

        {/* Input card */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, delay: 0.3 }}
          className="mx-auto mt-10 max-w-2xl rounded-xl border border-border bg-background shadow-elevated"
        >
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask Enter to build a dashboard with charts..."
            rows={3}
            className="w-full resize-none rounded-t-xl bg-transparent px-5 py-4 text-sm text-foreground placeholder:text-muted-foreground focus:outline-none sm:text-base"
          />

          <div className="flex items-center justify-between border-t border-border px-3 py-2">
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="icon-sm" className="text-muted-foreground">
                <Plus className="h-4 w-4" />
              </Button>
              <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-muted-foreground">
                <Sparkles className="h-3.5 w-3.5" />
                Plan
              </Button>
              <Button variant="ghost" size="sm" className="gap-1.5 text-xs text-muted-foreground">
                <Dices className="h-3.5 w-3.5" />
                Good Luck
              </Button>
            </div>

            <Button
              size="sm"
              className="gap-1.5 rounded-lg"
              onClick={handleStart}
            >
              Start Building
              <ArrowUp className="h-3.5 w-3.5" />
            </Button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
