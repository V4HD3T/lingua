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

/**
 * v0.1.8. The dedup above is per *tab* -- module state -- while the tokens
 * it guards live in localStorage, which every tab of the origin shares.
 * Two tabs therefore each deduped perfectly on their own and still sent
 * the same single-use refresh token, and the loser was read as a stolen
 * token being replayed: the person was logged out of every session they
 * had, for opening a second tab.
 *
 * A second tab can't be spawned inside vitest, so what's pinned here is
 * the mechanism that makes one unnecessary: the refresh runs inside a Web
 * Lock, and on the far side of that lock the tab re-reads localStorage
 * before deciding it still needs to refresh at all.
 */
describe("cross-tab refresh coordination", () => {
  beforeEach(() => {
    setTokens("old-access", "old-refresh");
    vi.unstubAllGlobals();
  });

  function lockManagerSpy(onAcquire?: () => void) {
    const request = vi.fn(async (_name: string, callback: () => Promise<unknown>) => {
      onAcquire?.();
      return callback();
    });
    vi.stubGlobal("navigator", { locks: { request } });
    return request;
  }

  it("refreshes while holding a cross-tab lock", async () => {
    const request = lockManagerSpy();
    vi.stubGlobal("fetch", vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) {
        return jsonRes(200, { access_token: "new-access", refresh_token: "new-refresh" });
      }
      return authHeader(init) === "Bearer new-access"
        ? jsonRes(200, { ok: true })
        : jsonRes(401, { detail: "Invalid or expired session" });
    }));

    await apiRequest("/protected", { auth: true });

    expect(request).toHaveBeenCalledTimes(1);
    expect(request.mock.calls[0][0]).toBe("lingua-token-refresh");
  });

  it("uses the token another tab already fetched instead of refreshing again", async () => {
    // The other tab wins the lock, refreshes, and writes its result to the
    // shared localStorage. This tab then acquires the lock and must notice
    // that -- spending the refresh token a second time is exactly what
    // tripped the backend's reuse detection.
    lockManagerSpy(() => setTokens("other-tabs-access", "other-tabs-refresh"));

    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) {
        throw new Error("refreshed again despite another tab having already done it");
      }
      return authHeader(init) === "Bearer other-tabs-access"
        ? jsonRes(200, { ok: true })
        : jsonRes(401, { detail: "Invalid or expired session" });
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiRequest<{ ok: boolean }>("/protected", { auth: true });

    expect(result.ok).toBe(true);
    const refreshCalls = fetchMock.mock.calls.filter(([url]) =>
      String(url).endsWith("/auth/refresh")
    );
    expect(refreshCalls).toHaveLength(0);
    // ...and the other tab's tokens are left intact, not rotated past.
    expect(getRefreshToken()).toBe("other-tabs-refresh");
  });

  it("still refreshes when the stored token is the stale one it just used", async () => {
    // The guard must not swallow genuine refreshes: nothing changed in
    // localStorage while waiting, so this tab is the one that has to go.
    lockManagerSpy();
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) {
        return jsonRes(200, { access_token: "new-access", refresh_token: "new-refresh" });
      }
      return authHeader(init) === "Bearer new-access"
        ? jsonRes(200, { ok: true })
        : jsonRes(401, { detail: "Invalid or expired session" });
    });
    vi.stubGlobal("fetch", fetchMock);

    await apiRequest("/protected", { auth: true });

    expect(getAccessToken()).toBe("new-access");
  });

  it("falls back to refreshing directly where Web Locks are unavailable", async () => {
    // Safari before 15.4. The backend's grace window is what covers this
    // path; the client must still work rather than throw.
    vi.stubGlobal("navigator", {});
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url).endsWith("/auth/refresh")) {
        return jsonRes(200, { access_token: "new-access", refresh_token: "new-refresh" });
      }
      return authHeader(init) === "Bearer new-access"
        ? jsonRes(200, { ok: true })
        : jsonRes(401, { detail: "Invalid or expired session" });
    });
    vi.stubGlobal("fetch", fetchMock);

    const result = await apiRequest<{ ok: boolean }>("/protected", { auth: true });

    expect(result.ok).toBe(true);
    expect(getAccessToken()).toBe("new-access");
  });
});
