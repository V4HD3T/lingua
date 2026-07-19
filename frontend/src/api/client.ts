const API_BASE_URL: string = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

const ACCESS_TOKEN_KEY = "lingua_token";
const REFRESH_TOKEN_KEY = "lingua_refresh_token";

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  form?: Record<string, string>;
  auth?: boolean;
}

export function getAccessToken(): string | null {
  return localStorage.getItem(ACCESS_TOKEN_KEY);
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_TOKEN_KEY);
}

export function setTokens(accessToken: string, refreshToken: string): void {
  localStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  localStorage.setItem(REFRESH_TOKEN_KEY, refreshToken);
}

export function clearTokens(): void {
  localStorage.removeItem(ACCESS_TOKEN_KEY);
  localStorage.removeItem(REFRESH_TOKEN_KEY);
}

// The access token is short-lived on purpose (see backend/README.md).
// Rather than make every page deal with expiry, apiRequest transparently
// refreshes and retries once on a 401. Concurrent requests that all hit a
// 401 around the same time share a single in-flight refresh call instead
// of each racing to rotate the refresh token themselves -- the backend
// treats a refresh token as single-use, so two simultaneous refresh calls
// would otherwise have one of them fail and (by design, see backend's
// reuse-detection) invalidate the whole session.
let refreshPromise: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (refreshPromise) return refreshPromise;

  refreshPromise = (async () => {
    const refreshToken = getRefreshToken();
    if (!refreshToken) return null;

    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        clearTokens();
        return null;
      }
      const data = await response.json();
      setTokens(data.access_token, data.refresh_token);
      return data.access_token as string;
    } catch {
      return null;
    }
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
}

async function doFetch(path: string, method: string, headers: Record<string, string>, requestBody: BodyInit | undefined) {
  return fetch(`${API_BASE_URL}${path}`, { method, headers, body: requestBody });
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, form, auth = false } = options;

  const headers: Record<string, string> = {};
  let requestBody: BodyInit | undefined;

  if (form) {
    headers["Content-Type"] = "application/x-www-form-urlencoded";
    requestBody = new URLSearchParams(form).toString();
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    requestBody = JSON.stringify(body);
  }

  if (auth) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  let response = await doFetch(path, method, headers, requestBody);

  if (auth && response.status === 401 && getRefreshToken()) {
    const newAccessToken = await refreshAccessToken();
    if (newAccessToken) {
      headers["Authorization"] = `Bearer ${newAccessToken}`;
      response = await doFetch(path, method, headers, requestBody);
    }
  }

  if (!response.ok) {
    let detail = "Something went wrong";
    try {
      const errJson = await response.json();
      detail = errJson.detail ?? detail;
    } catch {
      // response wasn't JSON, fall back to the default message
    }
    throw new ApiError(detail, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
