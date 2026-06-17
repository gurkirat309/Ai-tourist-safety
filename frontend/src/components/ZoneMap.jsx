import { useEffect } from "react";
import L from "leaflet";
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  CircleMarker,
  Popup,
  useMap,
} from "react-leaflet";
import { ZONE_COLORS, titleCase, fmtTime } from "../lib/format";

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
}) {
  return (
    <div style={{ height }}>
      <MapContainer center={center} zoom={zoom} scrollWheelZoom>
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {fit && <FitToZones geojson={geojson} />}
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
