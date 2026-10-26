import { afterEach, describe, expect, it, vi } from "vitest";

import {
  ApiError,
  apiFetch,
  apiUrl,
  getHealth,
  setUnauthorizedHandler,
} from "./client";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

describe("apiUrl", () => {
  it("uses the default base URL and the /api/v1 prefix", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "");
    expect(apiUrl("/health")).toBe("http://localhost:8000/api/v1/health");
  });

  it("uses NEXT_PUBLIC_API_BASE_URL when set", () => {
    vi.stubEnv("NEXT_PUBLIC_API_BASE_URL", "https://api.example.com/");
    expect(apiUrl("health")).toBe("https://api.example.com/api/v1/health");
  });
});

describe("apiFetch", () => {
  it("sends credentials and returns parsed JSON", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      jsonResponse({ status: "ok", database: "ok", version: "0.1.0" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    const health = await getHealth();

    expect(health).toEqual({ status: "ok", database: "ok", version: "0.1.0" });
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/api\/v1\/health$/);
    expect(init.credentials).toBe("include");
  });

  it("turns the error envelope into an ApiError with the backend code", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "not_found", message: "Not found." } }, 404),
      ),
    );

    const error = await apiFetch("/missing").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ code: "not_found", message: "Not found.", status: 404 });
  });

  it("falls back to unknown_error when the body is not an envelope", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("Bad gateway", { status: 502 })));

    await expect(apiFetch("/x")).rejects.toMatchObject({ code: "unknown_error", status: 502 });
  });

  it("uses network_error when fetch itself fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("Failed to fetch")));

    await expect(apiFetch("/x")).rejects.toMatchObject({ code: "network_error", status: 0 });
  });

  it("echoes the CSRF cookie in the X-CSRF-Token header on unsafe requests", async () => {
    document.cookie = "csrf_token=abc123";
    const fetchMock = vi.fn().mockImplementation(async () => jsonResponse({ message: "ok" }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/auth/sign-out", { method: "POST" });
    await apiFetch("/me", { method: "GET" });

    const postHeaders = new Headers((fetchMock.mock.calls[0] as [string, RequestInit])[1].headers);
    expect(postHeaders.get("X-CSRF-Token")).toBe("abc123");
    const getHeaders = new Headers((fetchMock.mock.calls[1] as [string, RequestInit])[1].headers);
    expect(getHeaders.get("X-CSRF-Token")).toBeNull();
    document.cookie = "csrf_token=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
  });

  it("rejects a 2xx with an empty body as invalid_response", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 200 })));

    await expect(apiFetch("/x")).rejects.toMatchObject({ code: "invalid_response", status: 200 });
  });

  it("rejects a 2xx whose body is not JSON as invalid_response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response("<html>Gateway</html>", { status: 200 })),
    );

    await expect(apiFetch("/x")).rejects.toMatchObject({ code: "invalid_response", status: 200 });
  });
});

describe("setUnauthorizedHandler", () => {
  afterEach(() => setUnauthorizedHandler(null));

  it("calls the registered handler on a 401 and still throws the error", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "not_authenticated", message: "Please sign in." } }, 401),
      ),
    );

    await expect(apiFetch("/me", { method: "PATCH", body: "{}" })).rejects.toMatchObject({
      code: "not_authenticated",
      status: 401,
    });
    expect(handler).toHaveBeenCalledTimes(1);
  });

  it("leaves a 403 and a 2xx to the caller", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(
          jsonResponse({ error: { code: "forbidden", message: "Not allowed." } }, 403),
        )
        .mockResolvedValueOnce(jsonResponse({ message: "ok" })),
    );

    await expect(apiFetch("/x")).rejects.toMatchObject({ code: "forbidden", status: 403 });
    await expect(apiFetch("/x")).resolves.toEqual({ message: "ok" });
    expect(handler).not.toHaveBeenCalled();
  });

  it("does nothing on a 401 once the handler is cleared", async () => {
    const handler = vi.fn();
    setUnauthorizedHandler(handler);
    setUnauthorizedHandler(null);
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        jsonResponse({ error: { code: "not_authenticated", message: "Please sign in." } }, 401),
      ),
    );

    await expect(apiFetch("/me")).rejects.toMatchObject({ status: 401 });
    expect(handler).not.toHaveBeenCalled();
  });
});
