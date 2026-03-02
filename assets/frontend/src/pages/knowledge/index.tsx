import { RefreshCw, Database, FileStack, AlertTriangle } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import Navbar from "@/components/layout/Navbar";
import UploadZone from "@/components/knowledge/UploadZone";
import SourceTable from "@/components/knowledge/SourceTable";
import { useKnowledge } from "@/hooks/use-knowledge";

export default function KnowledgePage() {
  const {
    sources,
    totalVectors,
    loading,
    error,
    syncing,
    uploading,
    uploadTasks,
    refresh,
    toggleSource,
    selectAll,
    deselectAll,
    deleteSourceByName,
    uploadFiles,
    dismissTask,
    triggerSync,
  } = useKnowledge();

  return (
    <div className="flex min-h-screen flex-col bg-background">
      <Navbar compact />

      <main className="mx-auto w-full max-w-3xl flex-1 px-4 py-8 sm:px-6">
        {/* Page header */}
        <div className="mb-8">
          <h1 className="text-2xl font-bold tracking-tight">Knowledge Base</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Upload documents, manage sources, and control RAG retrieval.
          </p>
        </div>

        {/* Upload zone */}
        <section className="mb-8">
          <UploadZone
            uploading={uploading}
            uploadTasks={uploadTasks}
            onUpload={uploadFiles}
            onDismissTask={dismissTask}
          />
        </section>

        {/* Status bar */}
        <section className="mb-6 flex flex-wrap items-center gap-4 rounded-lg border border-border bg-muted/20 px-4 py-3">
          <div className="flex items-center gap-2 text-sm">
            <FileStack className="h-4 w-4 text-muted-foreground" />
            <span>
              <strong>{sources.length}</strong> sources
            </span>
          </div>

          <div className="flex items-center gap-2 text-sm">
            <Database className="h-4 w-4 text-muted-foreground" />
            <span>
              <strong>{totalVectors.toLocaleString()}</strong> vectors
            </span>
          </div>

          <div className="ml-auto flex gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={refresh}
              disabled={loading}
            >
              <RefreshCw
                className={cn("mr-1.5 h-3.5 w-3.5", loading && "animate-spin")}
              />
              Refresh
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={triggerSync}
              disabled={syncing}
            >
              <RefreshCw
                className={cn(
                  "mr-1.5 h-3.5 w-3.5",
                  syncing && "animate-spin",
                )}
              />
              Sync
            </Button>
          </div>
        </section>

        {/* Error message */}
        {error && (
          <div className="mb-6 flex items-center gap-2 rounded-lg border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">
            <AlertTriangle className="h-4 w-4 shrink-0" />
            {error}
          </div>
        )}

        {/* Source table */}
        <section>
          {loading && sources.length === 0 ? (
            <div className="flex items-center justify-center py-12">
              <RefreshCw className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <SourceTable
              sources={sources}
              onToggle={toggleSource}
              onDelete={deleteSourceByName}
              onSelectAll={selectAll}
              onDeselectAll={deselectAll}
            />
          )}
        </section>
      </main>
    </div>
  );
}
