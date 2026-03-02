import { get, post, del } from "@/lib/api-client";

// ── Types ────────────────────────────────────────────────

export interface VectorCountsResponse {
  sources: string[];
  total_vectors: number;
  source_vectors: Record<string, number>;
  status: string;
  message: string;
}

export interface KnowledgeStatus {
  status: string;
  config: { sources: string[] };
  files: { sources: string[] };
  vectors: { sources: string[] };
  issues: string[];
  summary: string;
}

export interface KnowledgeSyncResult {
  status: string;
  message: string;
  results: {
    indexed: string[];
    removed_from_config: string[];
    removed_vectors: string[];
    errors: string[];
  };
}

export interface KnowledgeDeleteResult {
  status: string;
  message: string;
  results: {
    removed_from_config: boolean;
    deleted_vectors: boolean;
    deleted_file: boolean;
  };
}

export interface IngestResponse {
  task_id: string;
  status: string;
  files: string[];
  message: string;
}

export interface IngestStatusResponse {
  status: string;
}

export interface ReindexResponse {
  status: string;
  message: string;
  reindexed: string[];
}

// ── API Functions ────────────────────────────────────────

/** Get sources with vector counts */
export function getVectorCounts(): Promise<VectorCountsResponse> {
  return get<VectorCountsResponse>("/api/v1/sources/vector-counts");
}

/** Get knowledge sync status (3-layer reconciliation) */
export function getKnowledgeStatus(): Promise<KnowledgeStatus> {
  return get<KnowledgeStatus>("/api/v1/knowledge/status");
}

/** Trigger knowledge sync */
export function syncKnowledge(): Promise<KnowledgeSyncResult> {
  return post<KnowledgeSyncResult>("/api/v1/knowledge/sync");
}

/** Delete a knowledge source (config + vectors + file) */
export function deleteKnowledgeSource(
  name: string,
): Promise<KnowledgeDeleteResult> {
  return del<KnowledgeDeleteResult>(
    `/api/v1/knowledge/sources/${encodeURIComponent(name)}`,
  );
}

/** Upload files for ingestion (multipart/form-data) */
export async function ingestFiles(files: File[]): Promise<IngestResponse> {
  const formData = new FormData();
  for (const file of files) {
    formData.append("files", file);
  }

  const res = await fetch("/api/v1/ingest", {
    method: "POST",
    body: formData,
  });

  if (!res.ok) {
    const body = await res.json().catch(() => null);
    const msg = body?.error?.message ?? res.statusText;
    throw new Error(msg);
  }

  const body = await res.json();
  if (!body.data) {
    throw new Error("Unexpected response: missing data");
  }
  return body.data as IngestResponse;
}

/** Poll ingestion task status */
export function getIngestStatus(taskId: string): Promise<IngestStatusResponse> {
  return get<IngestStatusResponse>(`/api/v1/ingest/status/${taskId}`);
}

/** Re-index sources with zero vectors */
export function reindexSources(): Promise<ReindexResponse> {
  return post<ReindexResponse>("/api/v1/sources/reindex");
}

/** Delete a source (config + vectors only, keeps file) */
export function deleteSource(name: string): Promise<unknown> {
  return del(`/api/v1/sources/${encodeURIComponent(name)}`);
}
