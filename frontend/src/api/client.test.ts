import { beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiRequest, getAccessToken, getRefreshToken, setTokens } from "./client";

/** Response factory -- vitest's Node runtime ships the real Response. */
function jsonRes(status: number, body: unknown) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function authHeader(init?: RequestInit): string | undefined {
  return (init?.headers as Record<string, string> | undefined)?.["Authorization"];
}

describe("apiRequest token refresh", () => {
  beforeEach(() => {
    setTokens("old-access", "old-refresh");
  });

  it("transparently refreshes and retries once on a 401", async () => {
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) {
        return jsonRes(200, { access_token: "new-access", refresh_token: "new-refresh" });
      }
      return authHeader(init) === "Bearer new-access"
        ? jsonRes(200, { value: 42 })
        : jsonRes(401, { detail: "Invalid or expired session" });
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiRequest<{ value: number }>("/protected", { auth: true });

    expect(result.value).toBe(42);
    expect(fetchMock).toHaveBeenCalledTimes(3); // 401 -> refresh -> retry
    expect(getAccessToken()).toBe("new-access");
    expect(getRefreshToken()).toBe("new-refresh");
    expect(authHeader(fetchMock.mock.calls[2][1])).toBe("Bearer new-access");
  });

  it("clears the session and surfaces the original 401 when refresh is rejected", async () => {
    const fetchMock = vi.fn(async (url: RequestInfo | URL) => {
      if (String(url).endsWith("/auth/refresh")) {
        return jsonRes(401, { detail: "Invalid refresh token" });
      }
      return jsonRes(401, { detail: "Invalid or expired session" });
    });
    vi.stubGlobal("fetch", fetchMock);

    const failure = await apiRequest("/protected", { auth: true }).catch((e) => e);

    expect(failure).toBeInstanceOf(ApiError);
    expect((failure as ApiError).status).toBe(401);
    expect(getAccessToken()).toBeNull();
    expect(getRefreshToken()).toBeNull();
  });

  it("shares ONE refresh across concurrent 401s (single-use refresh tokens)", async () => {
    let refreshCalls = 0;
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) {
        refreshCalls += 1;
        // small real-timer delay so both callers are in flight together
        await new Promise((resolve) => setTimeout(resolve, 10));
        return jsonRes(200, { access_token: "new-access", refresh_token: "new-refresh" });
      }
      return authHeader(init) === "Bearer new-access"
        ? jsonRes(200, { ok: true })
        : jsonRes(401, { detail: "Invalid or expired session" });
    });
    vi.stubGlobal("fetch", fetchMock);

    const [a, b] = await Promise.all([
      apiRequest<{ ok: boolean }>("/one", { auth: true }),
      apiRequest<{ ok: boolean }>("/two", { auth: true }),
    ]);

    expect(a.ok && b.ok).toBe(true);
    // Two racing refreshes would rotate the single-use token twice; the
    // backend's reuse detection would then kill the whole session.
    expect(refreshCalls).toBe(1);
  });
});
