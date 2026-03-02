import { useCallback, useRef, useState } from "react";
import {
  Upload,
  FileText,
  X,
  Loader2,
  CheckCircle2,
  AlertCircle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { UploadTask } from "@/hooks/use-knowledge";

interface UploadZoneProps {
  uploading: boolean;
  uploadTasks: UploadTask[];
  onUpload: (files: File[]) => void;
  onDismissTask: (taskId: string) => void;
}

const ACCEPTED_TYPES = ".pdf,.txt,.md,.csv,.json,.html,.htm,.doc,.docx";

function statusLabel(status: string): string {
  switch (status) {
    case "queued":
      return "Queued";
    case "saving_files":
      return "Saving files...";
    case "loading_documents":
      return "Loading documents...";
    case "indexing_documents":
      return "Indexing vectors...";
    case "completed":
      return "Completed";
    default:
      if (status.startsWith("failed")) return "Failed";
      return status;
  }
}

function statusProgress(status: string): number {
  switch (status) {
    case "queued":
      return 10;
    case "saving_files":
      return 30;
    case "loading_documents":
      return 55;
    case "indexing_documents":
      return 80;
    case "completed":
      return 100;
    default:
      return 0;
  }
}

export default function UploadZone({
  uploading,
  uploadTasks,
  onUpload,
  onDismissTask,
}: UploadZoneProps) {
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const files = Array.from(e.dataTransfer.files);
      if (files.length > 0) onUpload(files);
    },
    [onUpload],
  );

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(e.target.files ?? []);
      if (files.length > 0) onUpload(files);
      e.target.value = "";
    },
    [onUpload],
  );

  return (
    <div className="space-y-3">
      {/* Drop zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload files — drag and drop or click to browse"
        onDragOver={(e) => {
          e.preventDefault();
          setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            inputRef.current?.click();
          }
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center gap-2 rounded-lg border-2 border-dashed px-6 py-8 transition-colors",
          dragOver
            ? "border-foreground/40 bg-muted/60"
            : "border-border hover:border-foreground/20 hover:bg-muted/30",
          uploading && "pointer-events-none opacity-60",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept={ACCEPTED_TYPES}
          onChange={handleFileChange}
          className="hidden"
        />
        {uploading ? (
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
        ) : (
          <Upload className="h-8 w-8 text-muted-foreground" />
        )}
        <p className="text-sm text-muted-foreground">
          {uploading
            ? "Uploading..."
            : "Drag & drop files here, or click to browse"}
        </p>
        <p className="text-xs text-muted-foreground/60">
          PDF, TXT, MD, CSV, JSON, HTML, DOC
        </p>
      </div>

      {/* Upload task list */}
      {uploadTasks.length > 0 && (
        <div className="space-y-2">
          {uploadTasks.map((task) => {
            const progress = statusProgress(task.status);
            const done = task.status === "completed";
            const failed = task.status.startsWith("failed");

            return (
              <div
                key={task.taskId}
                className="flex items-center gap-3 rounded-md border border-border bg-muted/20 px-3 py-2"
              >
                {done ? (
                  <CheckCircle2 className="h-4 w-4 shrink-0 text-foreground" />
                ) : failed ? (
                  <AlertCircle className="h-4 w-4 shrink-0 text-destructive" />
                ) : (
                  <FileText className="h-4 w-4 shrink-0 text-muted-foreground" />
                )}

                <div className="flex-1 min-w-0">
                  <p className="truncate text-sm">{task.files.join(", ")}</p>
                  <div className="mt-1 flex items-center gap-2">
                    <div className="h-1.5 flex-1 overflow-hidden rounded-full bg-muted">
                      <div
                        className={cn(
                          "h-full rounded-full transition-all duration-500",
                          failed ? "bg-destructive" : "bg-foreground",
                        )}
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                    <span className="shrink-0 text-xs text-muted-foreground">
                      {statusLabel(task.status)}
                    </span>
                  </div>
                </div>

                {(done || failed) && (
                  <Button
                    variant="ghost"
                    size="icon-sm"
                    aria-label="Dismiss"
                    onClick={() => onDismissTask(task.taskId)}
                    className="shrink-0"
                  >
                    <X className="h-3.5 w-3.5" />
                  </Button>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
