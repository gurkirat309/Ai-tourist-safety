// Thin fetch wrapper around the backend (proxied at /api in dev).
const BASE = "/api";
const TOKEN_KEY = "ts_token";

export function setToken(token) {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}
export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

async function request(path, { method = "GET", body, params } = {}) {
  let url = BASE + path;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    ).toString();
    if (qs) url += `?${qs}`;
  }
  const headers = {};
  if (body) headers["Content-Type"] = "application/json";
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(url, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail || res.statusText;
    const err = new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    err.status = res.status;
    throw err;
  }
  return data;
}

export const api = {
  health: () => request("/health/ready"),

  // Auth
  signup: (payload) => request("/auth/signup", { method: "POST", body: payload }),
  login: (payload) => request("/auth/login", { method: "POST", body: payload }),
  me: () => request("/auth/me"),

  // Tourists
  registerTourist: (payload) => request("/tourists", { method: "POST", body: payload }),
  getTourist: (id) => request(`/tourists/${id}`),

  // Location / orchestration
  ingestPing: (id, body) => request(`/tourists/${id}/pings`, { method: "POST", body }),
  panic: (id, body) => request(`/tourists/${id}/panic`, { method: "POST", body }),

  // Tourist self-service (/me)
  planTrip: (body) => request("/me/trip", { method: "POST", body }),
  myStatus: () => request("/me/status"),
  myPing: (body) => request("/me/pings", { method: "POST", body }),
  myPanic: (body) => request("/me/panic", { method: "POST", body }),

  // Risk
  areaRisk: (lat, lon, when) => request("/risk/area", { params: { lat, lon, when } }),
  zones: () => request("/risk/zones"),
  zonesGeojson: () => request("/risk/zones.geojson"),
  zoneAt: (lat, lon) => request("/risk/zone", { params: { lat, lon } }),

  // Authorities
  incidents: (params) => request("/incidents", { params }),
  incident: (id) => request(`/incidents/${id}`),
  alerts: (params) => request("/alerts", { params }),
};
