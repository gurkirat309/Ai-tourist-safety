/**
 * API client for the Tourist Safety backend.
 *
 * Unlike the police dashboard (which proxies /api through Vite), this app
 * calls the backend cross-origin at VITE_API_BASE. The backend permits it via
 * CORS_ORIGINS. An empty VITE_API_BASE means same-origin, which is what a
 * single-host deploy uses.
 */
import { getSync, set, remove, KEYS } from "./storage";

export const API_BASE = (import.meta.env.VITE_API_BASE || "").replace(/\/$/, "");

export function setToken(token) {
  if (token) set(KEYS.token, token);
  else remove(KEYS.token);
}
export function getToken() {
  return getSync(KEYS.token);
}

/** Thrown for any non-2xx response; `status` lets callers branch on 401 etc. */
export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// Network failures are common on a moving phone, so they get their own type:
// the UI shows "you're offline" rather than a scary error.
export class NetworkError extends Error {
  constructor(message = "Network unreachable") {
    super(message);
    this.name = "NetworkError";
  }
}

const DEFAULT_TIMEOUT_MS = 15000;

async function request(path, { method = "GET", body, params, timeout } = {}) {
  let url = API_BASE + path;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    ).toString();
    if (qs) url += `?${qs}`;
  }

  const headers = {
    // ngrok's free tier answers browser-looking requests with an interstitial
    // warning page. Without this header an API call would get that HTML
    // instead of JSON. Harmless on any other host.
    "ngrok-skip-browser-warning": "true",
  };
  if (body) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Without a timeout a request on a dead connection hangs forever and the
  // tracking loop stalls.
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeout ?? DEFAULT_TIMEOUT_MS);

  let res;
  try {
    res = await fetch(url, {
      method,
      headers,
      body: body ? JSON.stringify(body) : undefined,
      signal: ctrl.signal,
    });
  } catch (e) {
    throw new NetworkError(
      e.name === "AbortError" ? "Request timed out" : "Network unreachable"
    );
  } finally {
    clearTimeout(timer);
  }

  const text = await res.text();
  let data = null;
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = null;
    }
  }

  if (!res.ok) {
    // FastAPI validation errors arrive as a list of objects, not a string.
    let detail = data?.detail ?? res.statusText;
    if (Array.isArray(detail)) {
      detail = detail.map((d) => d.msg || JSON.stringify(d)).join("; ");
    } else if (typeof detail !== "string") {
      detail = JSON.stringify(detail);
    }
    throw new ApiError(detail, res.status);
  }
  return data;
}

export const api = {
  health: () => request("/health/ready", { timeout: 5000 }),

  // Auth
  signup: (payload) => request("/auth/signup", { method: "POST", body: payload }),
  login: (payload) => request("/auth/login", { method: "POST", body: payload }),
  me: () => request("/auth/me"),

  // Trip planning
  places: () => request("/places"),
  placeSearch: (q) => request("/places/search", { params: { q } }),
  // Routing calls OSRM and scores every sampled point against the risk model.
  // Warm that is ~1s, but the first call after a backend restart also loads
  // the model from disk, so this needs far more headroom than a normal call.
  planTrip: (body) => request("/me/trip", { method: "POST", body, timeout: 45000 }),

  // Live safety
  myStatus: () => request("/me/status"),
  myPing: (body) => request("/me/pings", { method: "POST", body }),
  myPanic: (body) => request("/me/panic", { method: "POST", body }),
  requestVoiceCall: (body) =>
    request("/voice/call-me", { method: "POST", body, timeout: 25000 }),

  // Map data
  zonesGeojson: () => request("/risk/zones.geojson"),
  areaRisk: (lat, lon, when) => request("/risk/area", { params: { lat, lon, when } }),
};
