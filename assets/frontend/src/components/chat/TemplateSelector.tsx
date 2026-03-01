import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { templates } from "@/lib/mock-templates";
import { Globe, ShoppingCart, LayoutDashboard, Briefcase, Rocket, Sparkles } from "lucide-react";

interface TemplateSelectorProps {
  open: boolean;
  onClose: () => void;
  onSelect: (templateId: string) => void;
}

const iconMap: Record<string, typeof Globe> = {
  blog: Globe,
  ecommerce: ShoppingCart,
  dashboard: LayoutDashboard,
  portfolio: Briefcase,
  landing: Rocket,
  "saas-app": Sparkles,
};

export default function TemplateSelector({
  open,
  onClose,
  onSelect,
}: TemplateSelectorProps) {
  return (
    <Dialog open={open} onOpenChange={(v) => !v && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-auto bg-background">
        <DialogHeader>
          <DialogTitle>Choose a Template</DialogTitle>
          <DialogDescription>
            Pick a starting point for your project. You can customize everything after.
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-3 sm:grid-cols-2">
          {templates.map((t) => {
            const Icon = iconMap[t.id] ?? Globe;
            return (
              <button
                key={t.id}
                onClick={() => {
                  onSelect(t.id);
                  onClose();
                }}
                className="group flex flex-col rounded-xl border border-border bg-background p-4 text-left transition-colors hover:bg-muted"
              >
                {/* Preview strip */}
                <div className="mb-3 h-24 w-full overflow-hidden rounded-lg border border-border bg-muted">
                  <iframe
                    srcDoc={t.previewHtml}
                    title={t.name}
                    className="h-[400px] w-[800px] origin-top-left scale-[0.3] pointer-events-none"
                    sandbox=""
                    tabIndex={-1}
                  />
                </div>

                <div className="flex items-center gap-2">
                  <Icon className="h-4 w-4 text-muted-foreground" />
                  <h4 className="font-semibold text-foreground">{t.name}</h4>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{t.description}</p>
                <Button size="sm" variant="secondary" className="mt-3 w-full opacity-0 transition-opacity group-hover:opacity-100">
                  Use Template
                </Button>
              </button>
            );
          })}
        </div>
      </DialogContent>
    </Dialog>
  );
}
