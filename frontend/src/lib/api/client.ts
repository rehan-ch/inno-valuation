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

// The signed-in shell registers what to do when the session has gone (any call answers
// 401): send the visitor to sign in. Nothing is registered on the auth pages or in tests,
// so a 401 there is just the error it always was.
let unauthorizedHandler: (() => void) | null = null;

/** Register the reaction to a 401 from any API call, or null to react no further. */
export function setUnauthorizedHandler(handler: (() => void) | null): void {
  unauthorizedHandler = handler;
}

// The backend sets a readable CSRF cookie (`__Host-csrf_token` on https, `csrf_token`
// locally) and expects its value back in this header on every unsafe request.
const CSRF_HEADER = "X-CSRF-Token";
const CSRF_COOKIE_NAMES = ["__Host-csrf_token", "csrf_token"];
const SAFE_METHODS = new Set(["GET", "HEAD", "OPTIONS"]);

function readCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  for (const part of document.cookie.split("; ")) {
    const eq = part.indexOf("=");
    if (eq === -1) continue;
    if (CSRF_COOKIE_NAMES.includes(part.slice(0, eq))) {
      return decodeURIComponent(part.slice(eq + 1));
    }
  }
  return null;
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

/** Sends the request and rejects with an ApiError on a network failure or a non-2xx
 * status. A 2xx comes back with its body text, still unparsed. */
async function send(path: string, init: RequestInit): Promise<{ response: Response; text: string }> {
  const headers = new Headers(init.headers);
  if (!headers.has("Accept")) headers.set("Accept", "application/json");
  // Only JSON strings get a JSON content type; FormData and Blob bodies set their own.
  if (typeof init.body === "string" && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const method = (init.method ?? "GET").toUpperCase();
  if (!SAFE_METHODS.has(method) && !headers.has(CSRF_HEADER)) {
    const token = readCsrfToken();
    if (token) headers.set(CSRF_HEADER, token);
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

  const text = await response.text();
  if (response.ok) return { response, text };

  if (response.status === 401) unauthorizedHandler?.();
  let body: unknown;
  try {
    body = text ? JSON.parse(text) : undefined;
  } catch {
    body = undefined;
  }
  if (isErrorEnvelope(body)) {
    throw new ApiError(body.error.code, body.error.message, response.status);
  }
  throw new ApiError(
    "unknown_error",
    `The server returned an error (${response.status}).`,
    response.status,
  );
}

/** A call whose 2xx answer is a JSON body. Every route answers with one, so an empty or
 * unparsable body is an error (code invalid_response). */
export async function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const { response, text } = await send(path, init);
  try {
    if (!text) throw new Error("empty body");
    return JSON.parse(text) as T;
  } catch {
    throw new ApiError(
      "invalid_response",
      "The server sent an answer we could not read.",
      response.status,
    );
  }
}

export function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  return apiFetch<T>(path, { ...init, method: "GET" });
}

export function postJson<T>(path: string, body?: unknown): Promise<T> {
  return apiFetch<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
}

export function patchJson<T>(path: string, body: unknown): Promise<T> {
  return apiFetch<T>(path, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteJson<T>(path: string): Promise<T> {
  return apiFetch<T>(path, { method: "DELETE" });
}

export function getHealth(init?: RequestInit): Promise<HealthOut> {
  return apiFetch<HealthOut>("/health", { ...init, method: "GET" });
}
