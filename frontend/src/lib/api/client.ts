import type { ApiErrorEnvelope, HealthOut } from "./types";

const DEFAULT_API_BASE_URL = "http://localhost:8000";
const API_PREFIX = "/api/v1";

export class ApiError extends Error {
  readonly code: string;
  readonly status: number;

  constructor(code: string, message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
  }
}

export function apiBaseUrl(): string {
  const base = process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_BASE_URL;
  return base.replace(/\/+$/, "");
}

export function apiUrl(path: string): string {
  const cleanPath = path.startsWith("/") ? path : `/${path}`;
  return `${apiBaseUrl()}${API_PREFIX}${cleanPath}`;
}

function isErrorEnvelope(value: unknown): value is ApiErrorEnvelope {
  if (typeof value !== "object" || value === null) return false;
  const error = (value as { error?: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as { code?: unknown }).code === "string" &&
    typeof (error as { message?: unknown }).message === "string"
  );
}

async function readJson(response: Response): Promise<unknown> {
  const text = await response.text();
  if (!text) return undefined;
  try {
    return JSON.parse(text);
  } catch {
    return undefined;
  }
}

export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  if (init.body !== undefined && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(apiUrl(path), {
      ...init,
      headers,
      credentials: "include",
    });
  } catch {
    throw new ApiError("network_error", "We could not reach the server.", 0);
  }

  const body = await readJson(response);

  if (!response.ok) {
    if (isErrorEnvelope(body)) {
      throw new ApiError(body.error.code, body.error.message, response.status);
    }
    throw new ApiError(
      "unknown_error",
      `The server returned an error (${response.status}).`,
      response.status,
    );
  }

  return body as T;
}

export function getHealth(init?: RequestInit): Promise<HealthOut> {
  return apiFetch<HealthOut>("/health", { ...init, method: "GET" });
}
