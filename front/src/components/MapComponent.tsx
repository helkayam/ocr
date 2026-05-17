/**
 * MapComponent — Leaflet map wrapper.
 * Renders GeoJSON layers, sensors (type-specific icons), geo features, and tags.
 * All layers are rendered simultaneously; clicking triggers fly-to, not visibility toggle.
 */
import { useEffect, useMemo, useRef } from 'react';
import type { Feature, GeoJsonProperties, Geometry } from 'geojson';
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Marker,
  Popup,
  Polyline,
  useMapEvents,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapLayer, MapTag, Sensor, GeoFeature } from '@/types/files';

// Fix Leaflet default icon paths broken by bundlers
// eslint-disable-next-line @typescript-eslint/no-explicit-any
delete (L.Icon.Default.prototype as any)._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
  iconUrl:       'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
  shadowUrl:     'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
});

export const LAYER_COLORS = [
  '#818cf8', '#34d399', '#fb923c', '#f472b6',
  '#60a5fa', '#facc15', '#a78bfa', '#2dd4bf',
];

function getLayerStyle(index: number, geoCategory?: string) {
  if (geoCategory && geoCategory.includes('building')) {
    return { color: '#3b82f6', weight: 2, fillColor: '#93c5fd', fillOpacity: 0.6 };
  }
  const color = LAYER_COLORS[index % LAYER_COLORS.length];
  return { color, weight: 2, fillColor: color, fillOpacity: 0.2 };
}

// ─── Custom icon factories ────────────────────────────────────────────────────

const SENSOR_ICON_CFG: Record<string, { bg: string; emoji: string }> = {
  SIREN:     { bg: '#ef4444', emoji: '🚨' },
  TERRORIST: { bg: '#7c3aed', emoji: '⚠️' },
  HAZMAT:    { bg: '#ea580c', emoji: '☢️' },
};

const GEO_FEATURE_ICON_CFG: Record<string, { bg: string; emoji: string; size?: number }> = {
  shelter:      { bg: '#dc2626', emoji: '🛡️', size: 40 },
  exit:         { bg: '#16a34a', emoji: '🚪' },
  muster_point: { bg: '#ca8a04', emoji: '👥' },
  extinguisher: { bg: '#ea580c', emoji: '🧯' },
  assembly:     { bg: '#7c3aed', emoji: '📍' },
  camera:       { bg: '#6b7280', emoji: '📷' },
  building:     { bg: '#78350f', emoji: '🏢' },
};

// User evacuation origin marker — blue pulsing ring
const ORIGIN_ICON = makeCircleIcon('👤', '#2563eb', 30);

const TAG_ICON_CFG: Record<string, { bg: string; emoji: string }> = {
  Camera:   { bg: '#6b7280', emoji: '📷' },
  Sensor:   { bg: '#f97316', emoji: '📡' },
  Shelter:  { bg: '#3b82f6', emoji: '🏠' },
  Building: { bg: '#78350f', emoji: '🏢' },
};

function makeCircleIcon(emoji: string, bg: string, size = 32) {
  return L.divIcon({
    className: '',
    html: `<div style="
      background:${bg};
      width:${size}px;height:${size}px;
      border-radius:50%;
      border:2px solid rgba(255,255,255,0.9);
      display:flex;align-items:center;justify-content:center;
      font-size:${Math.round(size * 0.44)}px;
      box-shadow:0 2px 8px rgba(0,0,0,0.45);
      cursor:pointer;
    ">${emoji}</div>`,
    iconSize: [size, size],
    iconAnchor: [size / 2, size / 2],
    popupAnchor: [0, -(size / 2 + 4)],
  });
}

function sensorIcon(sensorType: string) {
  const cfg = SENSOR_ICON_CFG[sensorType] ?? { bg: '#6b7280', emoji: '📡' };
  return makeCircleIcon(cfg.emoji, cfg.bg, 34);
}

function geoFeatureIcon(featureType: string) {
  const cfg = GEO_FEATURE_ICON_CFG[featureType] ?? { bg: '#6b7280', emoji: '📍' };
  return makeCircleIcon(cfg.emoji, cfg.bg, cfg.size ?? 30);
}

function tagIcon(color: string) {
  return L.divIcon({
    className: '',
    html: `<div style="
      width:24px;height:24px;border-radius:50% 50% 50% 0;
      background:${color};border:2px solid #fff;
      transform:rotate(-45deg);box-shadow:0 2px 6px rgba(0,0,0,.4)
    "></div>`,
    iconSize: [24, 24],
    iconAnchor: [12, 24],
    popupAnchor: [0, -28],
  });
}

// ─── Popup HTML builders ──────────────────────────────────────────────────────

function featurePopupHtml(feature: Feature<Geometry, GeoJsonProperties>, filename: string): string {
  const props = (feature.properties ?? {}) as Record<string, unknown>;
  const name =
    props['name']  ?? props['NAME']  ??
    props['label'] ?? props['LABEL'] ??
    props['title'] ?? props['TITLE'] ??
    props['id']    ?? props['ID']    ?? filename;

  const entries = Object.entries(props).filter(
    ([k, v]) => !['geometry', 'fid'].includes(k.toLowerCase()) && v != null && v !== ''
  );

  const rows = entries
    .slice(0, 8)
    .map(
      ([k, v]) =>
        `<tr>
          <td style="color:#9ca3af;padding:2px 8px 2px 0;font-size:11px;vertical-align:top;white-space:nowrap">${k}</td>
          <td style="font-size:11px;padding:2px 0;max-width:160px;word-break:break-word">${String(v)}</td>
        </tr>`
    )
    .join('');

  return `
    <div style="font-family:system-ui,sans-serif;min-width:150px;max-width:260px">
      <p style="font-weight:600;margin:0 0 5px;font-size:13px;border-bottom:1px solid #e5e7eb;padding-bottom:4px">
        ${String(name)}
      </p>
      ${rows ? `<table style="border-collapse:collapse;width:100%">${rows}</table>` : ''}
      ${entries.length > 8 ? `<p style="color:#9ca3af;font-size:10px;margin:3px 0 0">…and ${entries.length - 8} more</p>` : ''}
      <p style="color:#9ca3af;font-size:10px;margin:5px 0 0;border-top:1px solid #e5e7eb;padding-top:3px">${filename}</p>
    </div>
  `;
}

// ─── Inner map hooks ──────────────────────────────────────────────────────────

interface ClickHandlerProps {
  enabled: boolean;
  onClick: (lat: number, lng: number) => void;
}

function ClickHandler({ enabled, onClick }: ClickHandlerProps) {
  useMapEvents({
    click(e) {
      if (enabled) onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

function FlyToEffect({ bounds }: { bounds: L.LatLngBounds | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.isValid()) {
      map.flyToBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    }
  }, [bounds, map]);
  return null;
}

function FlyToCoordsEffect({ coords }: { coords: [number, number] | null }) {
  const map = useMap();
  useEffect(() => {
    if (coords) map.flyTo(coords, Math.max(map.getZoom(), 17), { animate: true, duration: 0.8 });
  }, [coords, map]);
  return null;
}

function AutoFitEffect({
  layers,
  sensors,
  geoFeatures,
}: {
  layers: MapLayer[];
  sensors: Sensor[];
  geoFeatures: GeoFeature[];
}) {
  const map = useMap();
  const hasFitted = useRef(false);

  useEffect(() => {
    if (hasFitted.current) return;
    const hasData =
      layers.length > 0 ||
      sensors.some(s => s.lat != null && s.lng != null) ||
      geoFeatures.some(f => f.lat != null && f.lng != null);
    if (!hasData) return;

    try {
      const children: L.Layer[] = [];
      for (const layer of layers) {
        try { children.push(L.geoJSON(layer.geojson as L.GeoJSONOptions['data'])); } catch {}
      }
      for (const s of sensors) {
        if (s.lat != null && s.lng != null) children.push(L.marker([s.lat!, s.lng!]));
      }
      for (const f of geoFeatures) {
        if (f.lat != null && f.lng != null) children.push(L.marker([f.lat, f.lng]));
      }
      if (children.length === 0) return;
      const bounds = L.featureGroup(children).getBounds();
      if (bounds.isValid()) {
        // Clamp zoom: never zoom out past level 13 even if content spans a large area
        const fitZoom = map.getBoundsZoom(bounds, false, L.point(40, 40));
        const clampedZoom = Math.max(fitZoom, 13);
        map.setView(bounds.getCenter(), clampedZoom, { animate: true });
        hasFitted.current = true;
      }
    } catch {}
  }, [layers, sensors, geoFeatures, map]);

  return null;
}

// ─── Public interface ─────────────────────────────────────────────────────────

interface MapComponentProps {
  layers?: MapLayer[];
  tags?: MapTag[];
  sensors?: Sensor[];
  geoFeatures?: GeoFeature[];
  tagMode?: boolean;
  originPickingMode?: boolean;
  userEvacOrigin?: { lat: number; lng: number } | null;
  onMapClick?: (lat: number, lng: number) => void;
  onTagDelete?: (tagId: string) => void;
  onSensorDelete?: (sensorId: string) => void;
  onGeoFeatureDelete?: (featureId: string) => void;
  onSensorSimulate?: (sensor: Sensor) => void;
  selectedLayerIndex?: number | null;
  selectedFeature?: object | null;
  onFeatureClick?: (feature: Feature<Geometry, GeoJsonProperties>) => void;
  flyToCoord?: [number, number] | null;
  evacuationRoute?: { from: [number, number]; to: [number, number] } | null;
  className?: string;
}

export function MapComponent({
  layers = [],
  tags = [],
  sensors = [],
  geoFeatures = [],
  tagMode = false,
  originPickingMode = false,
  userEvacOrigin = null,
  onMapClick,
  onTagDelete,
  onSensorDelete,
  onGeoFeatureDelete,
  onSensorSimulate,
  selectedLayerIndex = null,
  selectedFeature = null,
  onFeatureClick,
  flyToCoord = null,
  evacuationRoute = null,
  className = '',
}: MapComponentProps) {
  const center: [number, number] = [31.895, 35.015]; // Modi'in
  const zoom = 14;

  const targetBounds = useMemo<L.LatLngBounds | null>(() => {
    try {
      if (selectedFeature) {
        const b = L.geoJSON(selectedFeature as L.GeoJSONOptions['data']).getBounds();
        return b.isValid() ? b : null;
      }
      if (selectedLayerIndex != null && layers[selectedLayerIndex]) {
        const b = L.geoJSON(layers[selectedLayerIndex].geojson as L.GeoJSONOptions['data']).getBounds();
        return b.isValid() ? b : null;
      }
    } catch {
      // ignore invalid GeoJSON
    }
    return null;
  }, [selectedLayerIndex, selectedFeature, layers]);

  return (
    <div className={`relative ${className}`}>
      {tagMode && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] px-3 py-1.5 rounded-full bg-primary/90 text-primary-foreground text-xs font-medium shadow-lg">
          Click the map to place an entity
        </div>
      )}
      <MapContainer
        center={center}
        zoom={zoom}
        style={{ width: '100%', height: '100%', borderRadius: '0.75rem' }}
        className="z-0"
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        <ClickHandler enabled={tagMode || originPickingMode} onClick={onMapClick ?? (() => {})} />
        <FlyToEffect bounds={targetBounds} />
        <FlyToCoordsEffect coords={flyToCoord} />
        <AutoFitEffect layers={layers} sensors={sensors} geoFeatures={geoFeatures} />

        {/* ALL GeoJSON layers rendered simultaneously */}
        {layers.map((layer, i) => {
          const layerColor = LAYER_COLORS[i % LAYER_COLORS.length];
          // Map the plural DB category name to the singular feature-type key used by icon config
          const catIconKey: Record<string, string> = {
            shelters: 'shelter', cameras: 'camera', buildings: 'building',
          };
          const iconKey = layer.geo_category ? catIconKey[layer.geo_category] : undefined;
          return (
          <GeoJSON
            key={layer.layer_id}
            data={layer.geojson as L.GeoJSONOptions['data']}
            style={() => getLayerStyle(i, layer.geo_category)}
            pointToLayer={(_feature, latlng) => {
              if (iconKey) return L.marker(latlng, { icon: geoFeatureIcon(iconKey) });
              return L.circleMarker(latlng, {
                radius: 7,
                fillColor: layerColor,
                color: '#fff',
                weight: 1.5,
                opacity: 1,
                fillOpacity: 0.9,
              });
            }}
            onEachFeature={(feature, leafletLayer) => {
              const props = (feature.properties ?? {}) as Record<string, unknown>;
              const name =
                props['name']  ?? props['NAME']  ??
                props['label'] ?? props['LABEL'] ??
                props['title'] ?? props['TITLE'] ??
                props['id']    ?? props['ID']    ?? layer.filename;
              leafletLayer.bindTooltip(String(name), { direction: 'top', sticky: true });
              leafletLayer.bindPopup(featurePopupHtml(feature, layer.filename), { maxWidth: 280 });
              if (onFeatureClick) {
                leafletLayer.on('click', () => onFeatureClick(feature));
              }
            }}
          />
          );
        })}

        {/* Sensors — type-specific circle icons */}
        {sensors.filter(s => s.lat != null && s.lng != null).map(sensor => (
          <Marker
            key={sensor.sensor_id}
            position={[sensor.lat!, sensor.lng!]}
            icon={sensorIcon(sensor.sensor_type)}
          >
            <Popup maxWidth={220}>
              <div className="space-y-1.5 text-sm font-sans">
                <p className="font-semibold text-sm">{sensor.name}</p>
                <p className="text-xs text-gray-500">{sensor.sensor_type} sensor</p>
                <p className="text-xs font-mono text-gray-400">
                  {sensor.lat?.toFixed(5)}, {sensor.lng?.toFixed(5)}
                </p>
                <div className="flex gap-2 pt-1">
                  {onSensorSimulate && (
                    <button
                      onClick={() => onSensorSimulate(sensor)}
                      className="text-xs px-2 py-1 rounded bg-orange-100 text-orange-700 hover:bg-orange-200 font-medium"
                    >
                      Simulate Alert
                    </button>
                  )}
                  {onSensorDelete && (
                    <button
                      onClick={() => onSensorDelete(sensor.sensor_id)}
                      className="text-xs px-2 py-1 rounded bg-red-50 text-red-600 hover:bg-red-100"
                    >
                      Delete
                    </button>
                  )}
                </div>
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Geo features — category-specific circle icons */}
        {geoFeatures.filter(f => f.lat != null && f.lng != null).map(feat => (
          <Marker
            key={feat.feature_id}
            position={[feat.lat, feat.lng]}
            icon={geoFeatureIcon(feat.feature_type)}
          >
            <Popup maxWidth={200}>
              <div className="space-y-1 text-sm font-sans">
                <p className="font-semibold">{feat.label}</p>
                <p className="text-xs text-gray-500 capitalize">
                  {feat.feature_type.replace('_', ' ')}
                  {feat.floor ? ` · ${feat.floor}` : ''}
                </p>
                <p className="text-xs font-mono text-gray-400">
                  {feat.lat.toFixed(5)}, {feat.lng.toFixed(5)}
                </p>
                {onGeoFeatureDelete && (
                  <button
                    onClick={() => onGeoFeatureDelete(feat.feature_id)}
                    className="text-xs text-red-500 hover:underline pt-0.5"
                  >
                    Remove
                  </button>
                )}
              </div>
            </Popup>
          </Marker>
        ))}

        {/* Legacy map tags */}
        {tags.map(tag => (
          <Marker key={tag.tag_id} position={[tag.lat, tag.lng]} icon={tagIcon(tag.color)}>
            <Popup>
              <div className="text-sm space-y-1 font-sans">
                <p className="font-semibold">{tag.label}</p>
                <p className="text-gray-500 capitalize text-xs">{tag.tag_type}</p>
                {onTagDelete && (
                  <button
                    onClick={() => onTagDelete(tag.tag_id)}
                    className="text-red-500 text-xs hover:underline"
                  >
                    Delete tag
                  </button>
                )}
              </div>
            </Popup>
          </Marker>
        ))}

        {/* User evacuation origin marker */}
        {userEvacOrigin && (
          <Marker
            position={[userEvacOrigin.lat, userEvacOrigin.lng]}
            icon={ORIGIN_ICON}
          >
            <Popup maxWidth={180}>
              <div className="text-sm font-sans space-y-1">
                <p className="font-semibold">Your Location</p>
                <p className="text-xs font-mono text-gray-500">
                  {userEvacOrigin.lat.toFixed(5)}, {userEvacOrigin.lng.toFixed(5)}
                </p>
              </div>
            </Popup>
          </Marker>
        )}

        {/* Evacuation route — from user origin to nearest feature */}
        {evacuationRoute && (
          <Polyline
            positions={[evacuationRoute.from, evacuationRoute.to]}
            pathOptions={{ color: 'red', weight: 5, dashArray: '10, 10', opacity: 0.95 }}
          />
        )}
      </MapContainer>
    </div>
  );
}
