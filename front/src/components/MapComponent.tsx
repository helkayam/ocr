/**
 * MapComponent — Leaflet map wrapper.
 * Renders GeoJSON layers and user-placed tags.
 * Clicking the map in "tag mode" fires onMapClick with lat/lng.
 */
import { useEffect, useMemo } from 'react';
import {
  MapContainer,
  TileLayer,
  GeoJSON,
  Marker,
  Popup,
  useMapEvents,
  useMap,
} from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { MapLayer, MapTag } from '@/types/files';

// Fix Leaflet default icon paths broken by bundlers
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

function getLayerStyle(index: number) {
  const color = LAYER_COLORS[index % LAYER_COLORS.length];
  return { color, weight: 2, fillColor: color, fillOpacity: 0.2 };
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

/** Build HTML for a GeoJSON feature popup — shows all properties. */
function featurePopupHtml(feature: any, filename: string): string {
  const props = feature.properties ?? {};
  const name =
    props.name  ?? props.NAME  ??
    props.label ?? props.LABEL ??
    props.title ?? props.TITLE ??
    props.id    ?? props.ID    ?? filename;

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

  const overflow =
    entries.length > 8
      ? `<p style="color:#9ca3af;font-size:10px;margin:3px 0 0">…and ${entries.length - 8} more</p>`
      : '';

  return `
    <div style="font-family:system-ui,sans-serif;min-width:150px;max-width:260px">
      <p style="font-weight:600;margin:0 0 5px;font-size:13px;border-bottom:1px solid #e5e7eb;padding-bottom:4px">
        ${String(name)}
      </p>
      ${rows ? `<table style="border-collapse:collapse;width:100%">${rows}</table>` : ''}
      ${overflow}
      <p style="color:#9ca3af;font-size:10px;margin:5px 0 0;border-top:1px solid #e5e7eb;padding-top:3px">
        ${filename}
      </p>
    </div>
  `;
}

// ─── Inner components that require map context ────────────────────────────

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

/** Flies the map to `bounds` whenever it changes. Must be inside MapContainer. */
function FlyToEffect({ bounds }: { bounds: L.LatLngBounds | null }) {
  const map = useMap();
  useEffect(() => {
    if (bounds && bounds.isValid()) {
      map.flyToBounds(bounds, { padding: [40, 40], maxZoom: 16 });
    }
  }, [bounds]);
  return null;
}

// ─── Public interface ─────────────────────────────────────────────────────

interface MapComponentProps {
  layers?: MapLayer[];
  tags?: MapTag[];
  tagMode?: boolean;
  onMapClick?: (lat: number, lng: number) => void;
  onTagDelete?: (tagId: string) => void;
  /** Index into `layers` to fly to when changed. */
  selectedLayerIndex?: number | null;
  /** A single GeoJSON Feature object to fly to when changed. */
  selectedFeature?: object | null;
  className?: string;
}

export function MapComponent({
  layers = [],
  tags = [],
  tagMode = false,
  onMapClick,
  onTagDelete,
  selectedLayerIndex = null,
  selectedFeature = null,
  className = '',
}: MapComponentProps) {
  const center: [number, number] = [32.08, 34.78];
  const zoom = 12;

  // Compute the Leaflet bounds to fly to. selectedFeature takes priority.
  const targetBounds = useMemo<L.LatLngBounds | null>(() => {
    try {
      if (selectedFeature) {
        const b = L.geoJSON(selectedFeature as any).getBounds();
        return b.isValid() ? b : null;
      }
      if (selectedLayerIndex != null && layers[selectedLayerIndex]) {
        const b = L.geoJSON(layers[selectedLayerIndex].geojson as any).getBounds();
        return b.isValid() ? b : null;
      }
    } catch {
      // Invalid / empty GeoJSON — ignore
    }
    return null;
  }, [selectedLayerIndex, selectedFeature, layers]);

  return (
    <div className={`relative ${className}`}>
      {tagMode && (
        <div className="absolute top-3 left-1/2 -translate-x-1/2 z-[1000] px-3 py-1.5 rounded-full bg-primary/90 text-primary-foreground text-xs font-medium shadow-lg">
          Click the map to place a tag
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

        <ClickHandler enabled={tagMode} onClick={onMapClick ?? (() => {})} />
        <FlyToEffect bounds={targetBounds} />

        {layers.map((layer, i) => (
          <GeoJSON
            key={layer.layer_id}
            data={layer.geojson as any}
            style={getLayerStyle(i)}
            onEachFeature={(feature, leafletLayer) => {
              const props = feature.properties ?? {};
              const name =
                props.name  ?? props.NAME  ??
                props.label ?? props.LABEL ??
                props.title ?? props.TITLE ??
                props.id    ?? props.ID    ?? layer.filename;
              // Hover tooltip for quick identification
              leafletLayer.bindTooltip(String(name), { direction: 'top', sticky: true });
              // Click popup with full property table
              leafletLayer.bindPopup(featurePopupHtml(feature, layer.filename), { maxWidth: 280 });
            }}
          />
        ))}

        {tags.map(tag => (
          <Marker key={tag.tag_id} position={[tag.lat, tag.lng]} icon={tagIcon(tag.color)}>
            <Popup>
              <div className="text-sm space-y-1">
                <p className="font-semibold">{tag.label}</p>
                <p className="text-muted-foreground capitalize">{tag.tag_type}</p>
                {onTagDelete && (
                  <button
                    onClick={() => onTagDelete(tag.tag_id)}
                    className="text-destructive text-xs hover:underline"
                  >
                    Delete tag
                  </button>
                )}
              </div>
            </Popup>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
