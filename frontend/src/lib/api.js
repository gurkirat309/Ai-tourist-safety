// Thin fetch wrapper around the backend (proxied at /api in dev).
const BASE = "/api";

async function request(path, { method = "GET", body, params } = {}) {
  let url = BASE + path;
  if (params) {
    const qs = new URLSearchParams(
      Object.entries(params).filter(([, v]) => v !== undefined && v !== null)
    ).toString();
    if (qs) url += `?${qs}`;
  }
  const res = await fetch(url, {
    method,
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const detail = data?.detail || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

export const api = {
  health: () => request("/health/ready"),

  // Tourists
  registerTourist: (payload) => request("/tourists", { method: "POST", body: payload }),
  getTourist: (id) => request(`/tourists/${id}`),

  // Location / orchestration
  ingestPing: (id, body) => request(`/tourists/${id}/pings`, { method: "POST", body }),
  panic: (id, body) => request(`/tourists/${id}/panic`, { method: "POST", body }),

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
