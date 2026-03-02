import { get, post, del } from "@/lib/api-client";

// ---- Types ----

export interface RawMessage {
  type: "SystemMessage" | "HumanMessage" | "AIMessage";
  content: string;
}

export interface ChatMetadata {
  name: string;
  created_at?: string;
}

// SSE event types emitted by the backend
export interface SSETokenEvent {
  type: "token";
  data: string;
}
export interface SSENodeStartEvent {
  type: "node_start";
  data: string;
}
export interface SSEStoppedEvent {
  type: "stopped";
  message: string;
}
export interface SSEErrorEvent {
  type: "error";
  content: string;
}
export type SSEEvent =
  | SSETokenEvent
  | SSENodeStartEvent
  | SSEStoppedEvent
  | SSEErrorEvent;

// ---- API calls ----

export function listChats(): Promise<string[]> {
  return get<string[]>("/api/v1/chats");
}

export function createChat(): Promise<{ chat_id: string }> {
  return post<{ chat_id: string }>("/api/v1/chats");
}

export function deleteChat(chatId: string): Promise<unknown> {
  return del(`/api/v1/chats/${chatId}`);
}

export function getChatMessages(
  chatId: string,
  limit?: number,
): Promise<RawMessage[]> {
  const params = limit ? `?limit=${limit}` : "";
  return get<RawMessage[]>(`/api/v1/chats/${chatId}/messages${params}`);
}

export function getChatMetadata(chatId: string): Promise<ChatMetadata> {
  return get<ChatMetadata>(`/api/v1/chats/${chatId}/metadata`);
}

export function stopGeneration(
  chatId: string,
): Promise<{ chat_id: string; status: string }> {
  return post<{ chat_id: string; status: string }>(
    `/api/v1/chats/${chatId}/stop`,
  );
}

// ---- SSE streaming ----

export interface StreamCallbacks {
  onToken: (token: string) => void;
  onNodeStart?: (node: string) => void;
  onStopped?: (message: string) => void;
  onError?: (message: string) => void;
  onDone: () => void;
}

/**
 * Stream chat completions via SSE (POST, not EventSource).
 * Returns an AbortController so the caller can cancel the request.
 */
export function streamCompletion(
  chatId: string,
  message: string,
  callbacks: StreamCallbacks,
  imageId?: string,
): AbortController {
  const controller = new AbortController();

  (async () => {
    try {
      const body: Record<string, string> = { message };
      if (imageId) body.image_id = imageId;

      const res = await fetch(`/api/v1/chats/${chatId}/completions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!res.ok || !res.body) {
        callbacks.onError?.(`Request failed: ${res.status} ${res.statusText}`);
        callbacks.onDone();
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        // Keep the last (possibly incomplete) line in the buffer
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed || !trimmed.startsWith("data: ")) continue;

          const payload = trimmed.slice(6); // strip "data: "

          if (payload === "[DONE]") {
            callbacks.onDone();
            return;
          }

          try {
            const event = JSON.parse(payload) as SSEEvent;
            switch (event.type) {
              case "token":
                callbacks.onToken(event.data);
                break;
              case "node_start":
                callbacks.onNodeStart?.(event.data);
                break;
              case "stopped":
                callbacks.onStopped?.(event.message);
                break;
              case "error":
                callbacks.onError?.(event.content);
                break;
            }
          } catch {
            // skip malformed JSON lines
          }
        }
      }

      // Stream ended without [DONE]
      callbacks.onDone();
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        callbacks.onError?.((err as Error).message);
      }
      callbacks.onDone();
    }
  })();

  return controller;
}
