import { useCallback, useState } from "react";
import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

interface CodeBlockProps {
  language: string;
  code: string;
}

// Simple syntax highlighting with regex
function highlightSyntax(code: string, language: string): string {
  let html = code
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");

  if (language === "html" || language === "xml") {
    // Tags
    html = html.replace(
      /(&lt;\/?)([\w-]+)/g,
      '<span style="color:#569cd6">$1$2</span>'
    );
    // Attributes
    html = html.replace(
      /\s([\w-]+)=/g,
      ' <span style="color:#9cdcfe">$1</span>='
    );
    // Strings
    html = html.replace(
      /(".*?")/g,
      '<span style="color:#ce9178">$1</span>'
    );
    // Comments
    html = html.replace(
      /(&lt;!--.*?--&gt;)/gs,
      '<span style="color:#6a9955">$1</span>'
    );
  } else {
    // Keywords
    html = html.replace(
      /\b(const|let|var|function|return|import|export|from|if|else|for|while|class|new|this|async|await|try|catch)\b/g,
      '<span style="color:#569cd6">$1</span>'
    );
    // Strings
    html = html.replace(
      /(["'`])((?:(?!\1).)*?)\1/g,
      '<span style="color:#ce9178">$1$2$1</span>'
    );
    // Comments
    html = html.replace(
      /(\/\/.*)/g,
      '<span style="color:#6a9955">$1</span>'
    );
  }

  return html;
}

export default function CodeBlock({ language, code }: CodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code).then(() => {
      setCopied(true);
      toast.success("Copied to clipboard");
      setTimeout(() => setCopied(false), 2000);
    });
  }, [code]);

  const lines = code.split("\n");
  const highlighted = highlightSyntax(code, language);

  return (
    <div className="my-3 overflow-hidden rounded-lg border border-border bg-code text-code-foreground">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-border/30 bg-code px-4 py-2">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {language}
        </span>
        <Button
          variant="ghost"
          size="icon-sm"
          className="text-muted-foreground hover:text-foreground"
          onClick={handleCopy}
        >
          {copied ? (
            <Check className="h-3.5 w-3.5" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
        </Button>
      </div>

      {/* Code */}
      <div className="max-h-72 overflow-auto p-4">
        <div className="flex">
          {/* Line numbers */}
          <div className="mr-4 flex shrink-0 flex-col text-right text-xs leading-6 text-muted-foreground/40 select-none">
            {lines.map((_, i) => (
              <span key={i}>{i + 1}</span>
            ))}
          </div>
          {/* Code content */}
          <pre className="flex-1 overflow-x-auto text-xs leading-6">
            <code dangerouslySetInnerHTML={{ __html: highlighted }} />
          </pre>
        </div>
      </div>
    </div>
  );
}
