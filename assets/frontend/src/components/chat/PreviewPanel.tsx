import { useState } from "react";
import {
  Monitor,
  Tablet,
  Smartphone,
  Code2,
  Eye,
  Rocket,
  Download,
  Paintbrush,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import { toast } from "sonner";
import CodeBlock from "./CodeBlock";
import { cn } from "@/lib/utils";

interface PreviewPanelProps {
  previewHtml: string;
}

type Device = "desktop" | "tablet" | "mobile";

const deviceWidths: Record<Device, string> = {
  desktop: "100%",
  tablet: "768px",
  mobile: "375px",
};

export default function PreviewPanel({ previewHtml }: PreviewPanelProps) {
  const [device, setDevice] = useState<Device>("desktop");
  const isEmpty = !previewHtml;

  const handleAction = (action: string) => {
    toast.success(`${action} triggered! (Demo only)`);
  };

  return (
    <div className="flex h-full flex-col bg-surface">
      <Tabs defaultValue="preview" className="flex h-full flex-col">
        {/* Toolbar */}
        <div className="flex items-center justify-between border-b border-border bg-background px-3 py-1.5">
          <TabsList className="h-8 bg-transparent p-0">
            <TabsTrigger value="preview" className="h-7 gap-1.5 px-3 text-xs data-[state=active]:bg-muted">
              <Eye className="h-3.5 w-3.5" />
              Preview
            </TabsTrigger>
            <TabsTrigger value="code" className="h-7 gap-1.5 px-3 text-xs data-[state=active]:bg-muted">
              <Code2 className="h-3.5 w-3.5" />
              Code
            </TabsTrigger>
          </TabsList>

          <div className="flex items-center gap-1">
            {/* Device toggles */}
            <div className="mr-2 flex items-center gap-0.5 rounded-md border border-border p-0.5">
              {([
                ["desktop", Monitor],
                ["tablet", Tablet],
                ["mobile", Smartphone],
              ] as [Device, typeof Monitor][]).map(([d, Icon]) => (
                <button
                  key={d}
                  onClick={() => setDevice(d)}
                  className={cn(
                    "rounded p-1 transition-colors",
                    device === d
                      ? "bg-muted text-foreground"
                      : "text-muted-foreground hover:text-foreground"
                  )}
                >
                  <Icon className="h-3.5 w-3.5" />
                </button>
              ))}
            </div>

            {/* Actions */}
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => handleAction("Deploy")}
              disabled={isEmpty}
            >
              <Rocket className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => handleAction("Export")}
              disabled={isEmpty}
            >
              <Download className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="icon-sm"
              onClick={() => handleAction("Customize")}
              disabled={isEmpty}
            >
              <Paintbrush className="h-3.5 w-3.5" />
            </Button>
          </div>
        </div>

        {/* Preview tab */}
        <TabsContent value="preview" className="mt-0 flex-1 overflow-hidden">
          {isEmpty ? (
            <div className="flex h-full flex-col items-center justify-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
                <Eye className="h-7 w-7 text-muted-foreground" />
              </div>
              <h3 className="mt-4 font-semibold text-foreground">Preview will appear here</h3>
              <p className="mt-1 text-center text-sm text-muted-foreground">
                Start a conversation or select a template
                <br />
                to see a live preview.
              </p>
            </div>
          ) : (
            <div className="flex h-full items-start justify-center overflow-auto bg-muted/50 p-4">
              <div
                className="h-full overflow-hidden rounded-lg border border-border bg-background shadow-card transition-all duration-300"
                style={{ width: deviceWidths[device], maxWidth: "100%" }}
              >
                <iframe
                  srcDoc={previewHtml}
                  sandbox="allow-scripts"
                  title="Preview"
                  className="h-full w-full"
                  style={{ minHeight: "500px" }}
                />
              </div>
            </div>
          )}
        </TabsContent>

        {/* Code tab */}
        <TabsContent value="code" className="mt-0 flex-1 overflow-auto p-4">
          {isEmpty ? (
            <div className="flex h-full flex-col items-center justify-center">
              <Code2 className="h-10 w-10 text-muted-foreground" />
              <p className="mt-3 text-sm text-muted-foreground">
                Generated code will appear here.
              </p>
            </div>
          ) : (
            <CodeBlock language="html" code={previewHtml} />
          )}
        </TabsContent>
      </Tabs>
    </div>
  );
}
