import { get, post } from "@/lib/api-client";

export function getSelectedSources(): Promise<string[]> {
  return get<string[]>("/api/v1/selected-sources");
}

export function setSelectedSources(sources: string[]): Promise<unknown> {
  return post("/api/v1/selected-sources", { sources });
}

export function listSources(): Promise<string[]> {
  return get<string[]>("/api/v1/sources");
}
