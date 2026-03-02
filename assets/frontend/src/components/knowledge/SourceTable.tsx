import { useState } from "react";
import { Trash2, Loader2, Database } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Checkbox } from "@/components/ui/checkbox";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import type { SourceInfo } from "@/hooks/use-knowledge";

interface SourceTableProps {
  sources: SourceInfo[];
  onToggle: (name: string) => void;
  onDelete: (name: string) => void;
  onSelectAll: () => void;
  onDeselectAll: () => void;
}

export default function SourceTable({
  sources,
  onToggle,
  onDelete,
  onSelectAll,
  onDeselectAll,
}: SourceTableProps) {
  const [deletingName, setDeletingName] = useState<string | null>(null);
  const selectedCount = sources.filter((s) => s.selected).length;

  const handleDelete = async (name: string) => {
    setDeletingName(name);
    try {
      await onDelete(name);
    } finally {
      setDeletingName(null);
    }
  };

  if (sources.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed border-border py-12 text-muted-foreground">
        <Database className="h-8 w-8" />
        <p className="text-sm">No sources yet</p>
        <p className="text-xs">Upload documents above to get started</p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Bulk actions */}
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          {selectedCount} of {sources.length} selected
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={onSelectAll}>
            Select All
          </Button>
          <Button variant="outline" size="sm" onClick={onDeselectAll}>
            Deselect All
          </Button>
        </div>
      </div>

      {/* Source list */}
      <div className="divide-y divide-border rounded-lg border border-border">
        {sources.map((source) => (
          <div
            key={source.name}
            className="flex items-center gap-3 px-4 py-3 transition-colors hover:bg-muted/30"
          >
            <Checkbox
              checked={source.selected}
              onCheckedChange={() => onToggle(source.name)}
            />

            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium">{source.name}</p>
            </div>

            <span className="shrink-0 text-xs text-muted-foreground tabular-nums">
              {source.vectors.toLocaleString()} vectors
            </span>

            <AlertDialog>
              <AlertDialogTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon-sm"
                  className="shrink-0 text-muted-foreground hover:text-destructive"
                  disabled={deletingName === source.name}
                >
                  {deletingName === source.name ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </Button>
              </AlertDialogTrigger>
              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Delete source</AlertDialogTitle>
                  <AlertDialogDescription>
                    This will permanently remove <strong>{source.name}</strong>{" "}
                    from the knowledge base, including all indexed vectors and
                    the source file.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel>Cancel</AlertDialogCancel>
                  <AlertDialogAction onClick={() => handleDelete(source.name)}>
                    Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>
        ))}
      </div>
    </div>
  );
}
