import { useCallback, useEffect, useRef, useState } from "react";
import { getSelectedSources, setSelectedSources } from "@/lib/api/sources";
import {
  deleteKnowledgeSource,
  getIngestStatus,
  getVectorCounts,
  ingestFiles,
  syncKnowledge,
  type IngestStatusResponse,
  type VectorCountsResponse,
} from "@/lib/api/knowledge";

// ── Types ────────────────────────────────────────────────

export interface SourceInfo {
  name: string;
  vectors: number;
  selected: boolean;
}

export interface UploadTask {
  taskId: string;
  files: string[];
  status: string;
}

// ── Hook ─────────────────────────────────────────────────

export function useKnowledge() {
  const [sources, setSources] = useState<SourceInfo[]>([]);
  const [totalVectors, setTotalVectors] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [uploadTasks, setUploadTasks] = useState<UploadTask[]>([]);
  const [uploading, setUploading] = useState(false);

  const pollTimers = useRef<Map<string, ReturnType<typeof setInterval>>>(
    new Map(),
  );
  const mountedRef = useRef(true);

  // ── Fetch sources + vector counts + selection ──────────

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [counts, selected] = await Promise.all([
        getVectorCounts(),
        getSelectedSources(),
      ]);
      const selectedSet = new Set(selected);
      const merged: SourceInfo[] = counts.sources.map((name) => ({
        name,
        vectors: counts.source_vectors[name] ?? 0,
        selected: selectedSet.has(name),
      }));
      // Sort: selected first, then by name
      merged.sort((a, b) => {
        if (a.selected !== b.selected) return a.selected ? -1 : 1;
        return a.name.localeCompare(b.name);
      });
      setSources(merged);
      setTotalVectors(counts.total_vectors);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sources");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  // Cleanup poll timers on unmount
  useEffect(() => {
    const timers = pollTimers.current;
    return () => {
      mountedRef.current = false;
      for (const timer of timers.values()) clearInterval(timer);
      timers.clear();
    };
  }, []);

  // ── Toggle source selection ────────────────────────────

  const toggleSource = useCallback(async (name: string) => {
    let snapshot: SourceInfo[] = [];
    setSources((prev) => {
      snapshot = prev;
      return prev.map((s) =>
        s.name === name ? { ...s, selected: !s.selected } : s,
      );
    });

    const newSelected = snapshot
      .map((s) => (s.name === name ? { ...s, selected: !s.selected } : s))
      .filter((s) => s.selected)
      .map((s) => s.name);
    try {
      await setSelectedSources(newSelected);
    } catch {
      setSources(snapshot);
    }
  }, []);

  const selectAll = useCallback(async () => {
    let snapshot: SourceInfo[] = [];
    setSources((prev) => {
      snapshot = prev;
      return prev.map((s) => ({ ...s, selected: true }));
    });
    try {
      await setSelectedSources(snapshot.map((s) => s.name));
    } catch {
      setSources(snapshot);
    }
  }, []);

  const deselectAll = useCallback(async () => {
    let snapshot: SourceInfo[] = [];
    setSources((prev) => {
      snapshot = prev;
      return prev.map((s) => ({ ...s, selected: false }));
    });
    try {
      await setSelectedSources([]);
    } catch {
      setSources(snapshot);
    }
  }, []);

  // ── Delete source ─────────────────────────────────────

  const deleteSourceByName = useCallback(
    async (name: string) => {
      setSources((prev) => prev.filter((s) => s.name !== name));
      try {
        await deleteKnowledgeSource(name);
        await refresh();
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to delete source",
        );
        await refresh();
      }
    },
    [refresh],
  );

  // ── Upload files ──────────────────────────────────────

  const startPoll = useCallback(
    (taskId: string) => {
      const timer = setInterval(async () => {
        try {
          const status: IngestStatusResponse = await getIngestStatus(taskId);
          setUploadTasks((prev) =>
            prev.map((t) =>
              t.taskId === taskId ? { ...t, status: status.status } : t,
            ),
          );
          if (
            status.status === "completed" ||
            status.status.startsWith("failed")
          ) {
            clearInterval(timer);
            pollTimers.current.delete(taskId);
            // Refresh sources after completion (guard against unmounted)
            if (status.status === "completed" && mountedRef.current) {
              await refresh();
            }
          }
        } catch {
          clearInterval(timer);
          pollTimers.current.delete(taskId);
        }
      }, 2000);
      pollTimers.current.set(taskId, timer);
    },
    [refresh],
  );

  const uploadFiles = useCallback(
    async (files: File[]) => {
      if (files.length === 0) return;
      setUploading(true);
      setError(null);
      try {
        const result = await ingestFiles(files);
        const task: UploadTask = {
          taskId: result.task_id,
          files: result.files,
          status: result.status,
        };
        setUploadTasks((prev) => [task, ...prev]);
        startPoll(result.task_id);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to upload files");
      } finally {
        setUploading(false);
      }
    },
    [startPoll],
  );

  const dismissTask = useCallback((taskId: string) => {
    setUploadTasks((prev) => prev.filter((t) => t.taskId !== taskId));
    const timer = pollTimers.current.get(taskId);
    if (timer) {
      clearInterval(timer);
      pollTimers.current.delete(taskId);
    }
  }, []);

  // ── Sync ──────────────────────────────────────────────

  const triggerSync = useCallback(async () => {
    setSyncing(true);
    setError(null);
    try {
      await syncKnowledge();
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Sync failed");
    } finally {
      setSyncing(false);
    }
  }, [refresh]);

  return {
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
  };
}
