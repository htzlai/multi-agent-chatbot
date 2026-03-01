/**
 * Base API client for backend communication.
 *
 * In development, Vite proxy forwards /api → http://localhost:8000.
 * In production, the backend serves the frontend, so relative paths work.
 */

export class ApiError extends Error {
  constructor(
    public status: number,
    public code: string,
    message: string,
    public details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let code = "UNKNOWN";
    let message = res.statusText;
    let details: Record<string, unknown> | undefined;

    try {
      const body = await res.json();
      if (body.error) {
        code = body.error.code ?? code;
        message = body.error.message ?? message;
        details = body.error.details;
      }
    } catch {
      // response wasn't JSON — use statusText
    }

    throw new ApiError(res.status, code, message, details);
  }

  const body = await res.json();
  return body.data as T;
}

export async function get<T>(path: string): Promise<T> {
  const res = await fetch(path);
  return handleResponse<T>(res);
}

export async function post<T>(
  path: string,
  body?: unknown,
): Promise<T> {
  const res = await fetch(path, {
    method: "POST",
    headers: body != null ? { "Content-Type": "application/json" } : {},
    body: body != null ? JSON.stringify(body) : undefined,
  });
  return handleResponse<T>(res);
}

export async function patch<T>(
  path: string,
  body: unknown,
): Promise<T> {
  const res = await fetch(path, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return handleResponse<T>(res);
}

export async function del<T>(path: string): Promise<T> {
  const res = await fetch(path, { method: "DELETE" });
  return handleResponse<T>(res);
}
