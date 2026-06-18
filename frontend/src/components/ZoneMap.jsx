import { useEffect } from "react";
import L from "leaflet";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  CircleMarker,
  Polyline,
  Popup,
  useMap,
} from "react-leaflet";
import {
  ZONE_COLORS,
  TOURIST_STATUS_COLORS,
  riskLevel,
  titleCase,
  fmtTime,
} from "../lib/format";

const BENGALURU = [12.95, 77.62];

// Fit the view to the zone polygons once they load.
function FitToZones({ geojson }) {
  const map = useMap();
  useEffect(() => {
    if (!geojson?.features?.length) return;
    try {
      const bounds = L.geoJSON(geojson).getBounds();
      if (bounds.isValid()) map.fitBounds(bounds, { padding: [30, 30] });
    } catch {
      /* ignore */
    }
  }, [geojson, map]);
  return null;
}

// Pan to follow a moving point (e.g. the tourist during a simulated trip).
function Recenter({ center, follow }) {
  const map = useMap();
  useEffect(() => {
    if (follow && center) map.panTo(center);
  }, [center, follow, map]);
  return null;
}

function zoneStyle(feature) {
  const cat = feature.properties.risk_category;
  const color = ZONE_COLORS[cat] || "#64748b";
  return {
    color,
    weight: 2,
    fillColor: color,
    fillOpacity: feature.properties.restricted ? 0.28 : 0.14,
  };
}

function onEachZone(feature, layer) {
  const p = feature.properties;
  layer.bindTooltip(
    `${p.name} · ${titleCase(p.risk_category)}${p.restricted ? " · restricted" : ""}`,
    { sticky: true }
  );
}

export default function ZoneMap({
  geojson,
  incidents = [],
  marker = null,
  height = 460,
  center = BENGALURU,
  zoom = 12,
  fit = false,
  onIncidentClick,
  route = null,
  routeColor = "#2563eb",
  safetyPoints = [],
  follow = false,
  tourists = [],
  onTouristClick,
}) {
  return (
    <div style={{ height }}>
      <MapContainer center={center} zoom={zoom} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {fit && <FitToZones geojson={geojson} />}
        <Recenter center={center} follow={follow} />

        {route && route.length >= 2 && (
          <Polyline positions={route} pathOptions={{ color: routeColor, weight: 5, opacity: 0.75 }} />
        )}

        {safetyPoints
          .filter((p) => p.score != null)
          .map((p, i) => (
            <CircleMarker
              key={`sp-${i}`}
              center={[p.lat, p.lon]}
              radius={5}
              pathOptions={{
                color: riskLevel(p.score).color,
                fillColor: riskLevel(p.score).color,
                fillOpacity: 0.9,
              }}
            >
              <Popup>
                <div className="text-xs">
                  Safety: {riskLevel(p.score).label} ({p.score.toFixed(2)})
                </div>
              </Popup>
            </CircleMarker>
          ))}
        {geojson && (
          <GeoJSON
            key={geojson.features?.length || 0}
            data={geojson}
            style={zoneStyle}
            onEachFeature={onEachZone}
          />
        )}

        {incidents
          .filter((i) => i.location)
          .map((i) => (
            <CircleMarker
              key={i.id}
              center={[i.location.lat, i.location.lon]}
              radius={7}
              pathOptions={{ color: "#dc2626", fillColor: "#ef4444", fillOpacity: 0.9 }}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold">{titleCase(i.incident_type)}</div>
                  <div>Status: {i.status}</div>
                  <div>{fmtTime(i.detected_at)}</div>
                  {onIncidentClick && (
                    <button
                      onClick={() => onIncidentClick(i.id)}
                      className="mt-1 font-medium text-blue-600 hover:underline"
                    >
                      View details →
                    </button>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          ))}

        {tourists
          .filter((t) => t.last_position)
          .map((t) => (
            <CircleMarker
              key={t.id}
              center={[t.last_position.lat, t.last_position.lon]}
              radius={8}
              pathOptions={{
                color: "#1e293b",
                weight: 2,
                fillColor: TOURIST_STATUS_COLORS[t.status] || "#3b82f6",
                fillOpacity: 0.95,
              }}
            >
              <Popup>
                <div className="text-xs">
                  <div className="font-semibold">{t.display_name || "Tourist"}</div>
                  <div>Status: {t.status}</div>
                  {onTouristClick && (
                    <button
                      onClick={() => onTouristClick(t.id)}
                      className="mt-1 font-medium text-blue-600 hover:underline"
                    >
                      View details →
                    </button>
                  )}
                </div>
              </Popup>
            </CircleMarker>
          ))}

        {marker && (
          <CircleMarker
            center={[marker.lat, marker.lon]}
            radius={9}
            pathOptions={{ color: "#1d4ed8", fillColor: "#3b82f6", fillOpacity: 0.9 }}
          >
            <Popup>{marker.label || "Current location"}</Popup>
          </CircleMarker>
        )}
      </MapContainer>
    </div>
  );
}
