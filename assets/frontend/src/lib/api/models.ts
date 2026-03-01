import { get, post } from "@/lib/api-client";

export interface AvailableModels {
  models: string[];
}

export interface SelectedModel {
  model: string;
}

export function getAvailableModels(): Promise<AvailableModels> {
  return get<AvailableModels>("/api/v1/models/available");
}

export function getSelectedModel(): Promise<SelectedModel> {
  return get<SelectedModel>("/api/v1/models/selected");
}

export function setSelectedModel(model: string): Promise<unknown> {
  return post("/api/v1/models/selected", { model });
}
