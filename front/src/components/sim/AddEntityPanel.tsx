/**
 * AddEntityPanel — Right-side panel for placing sensors and geo features on the map.
 * Supports both manual coordinate input and map-click placement.
 */
import { motion } from 'framer-motion';
import { X, Crosshair, MapPin } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';

type SensorType = 'SIREN' | 'TERRORIST' | 'HAZMAT';
type EntityType = 'Sensor' | 'Camera' | 'Shelter' | 'Building';

interface AddEntityPanelProps {
  placementMode: boolean;
  onTogglePlacement: () => void;
  pendingCoord: { lat: number; lng: number } | null;
  onClearCoord: () => void;
  onCoordChange: (coord: { lat: number; lng: number }) => void;
  entityType: EntityType;
  onEntityTypeChange: (type: EntityType) => void;
  sensorType: SensorType;
  onSensorTypeChange: (type: SensorType) => void;
  onPlace: () => void;
  isPlacing: boolean;
  onClose: () => void;
}

const ENTITY_TYPES: { type: EntityType; emoji: string; label: string; color: string }[] = [
  { type: 'Sensor',   emoji: '📡', label: 'Sensor',   color: 'border-orange-500 bg-orange-500/10 text-orange-400' },
  { type: 'Camera',   emoji: '📷', label: 'Camera',   color: 'border-gray-400 bg-gray-500/10 text-gray-400' },
  { type: 'Shelter',  emoji: '🛡️', label: 'Shelter',  color: 'border-red-500 bg-red-500/10 text-red-400' },
  { type: 'Building', emoji: '🏢', label: 'Building', color: 'border-amber-700 bg-amber-800/10 text-amber-700' },
];

const SENSOR_TYPES: { type: SensorType; emoji: string; label: string }[] = [
  { type: 'SIREN',     emoji: '🚨', label: 'Missile Alarm' },
  { type: 'TERRORIST', emoji: '⚠️', label: 'Terrorist' },
  { type: 'HAZMAT',    emoji: '☢️', label: 'Hazmat' },
];

export function AddEntityPanel({
  placementMode,
  onTogglePlacement,
  pendingCoord,
  onClearCoord,
  onCoordChange,
  entityType,
  onEntityTypeChange,
  sensorType,
  onSensorTypeChange,
  onPlace,
  isPlacing,
  onClose,
}: AddEntityPanelProps) {
  const selectedEntity = ENTITY_TYPES.find(e => e.type === entityType)!;

  return (
    <motion.div
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', stiffness: 340, damping: 36 }}
      className="absolute top-0 right-0 bottom-0 w-full sm:w-[320px] z-[800] flex flex-col bg-card/95 backdrop-blur-xl border-l border-border overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-border bg-background/60 shrink-0">
        <h2 className="text-sm font-bold uppercase tracking-wider flex items-center gap-2">
          <MapPin className="h-4 w-4 text-primary" />
          Place Entity
        </h2>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Entity type grid */}
        <div className="space-y-2">
          <Label className="text-xs uppercase tracking-wide text-muted-foreground">Entity Type</Label>
          <div className="grid grid-cols-2 gap-2">
            {ENTITY_TYPES.map(et => (
              <button
                key={et.type}
                onClick={() => onEntityTypeChange(et.type)}
                className={cn(
                  'flex flex-col items-center gap-1.5 py-3 rounded-xl border-2 text-xs font-semibold transition-all',
                  entityType === et.type
                    ? et.color
                    : 'border-border text-muted-foreground hover:bg-muted/50'
                )}
              >
                <span className="text-xl">{et.emoji}</span>
                {et.label}
              </button>
            ))}
          </div>
        </div>

        {/* Sensor sub-type */}
        {entityType === 'Sensor' && (
          <div className="space-y-2">
            <Label className="text-xs uppercase tracking-wide text-muted-foreground">Sensor Type</Label>
            <div className="space-y-1.5">
              {SENSOR_TYPES.map(st => (
                <button
                  key={st.type}
                  onClick={() => onSensorTypeChange(st.type)}
                  className={cn(
                    'w-full flex items-center gap-2 px-3 py-2 rounded-xl border text-xs font-medium transition-all',
                    sensorType === st.type
                      ? 'bg-primary/10 border-primary text-primary'
                      : 'border-border text-muted-foreground hover:bg-muted/40'
                  )}
                >
                  <span className="text-base">{st.emoji}</span>
                  {st.label}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Coordinate entry */}
        <div className="space-y-2">
          <Label className="text-xs uppercase tracking-wide text-muted-foreground">Coordinates</Label>
          <div className="grid grid-cols-2 gap-2">
            <div>
              <Label className="text-xs text-muted-foreground mb-1 block">Latitude</Label>
              <Input
                type="number"
                step="0.00001"
                placeholder="32.080"
                value={pendingCoord?.lat ?? ''}
                onChange={e => {
                  const lat = parseFloat(e.target.value);
                  if (!isNaN(lat)) onCoordChange({ lat, lng: pendingCoord?.lng ?? 0 });
                }}
                className="h-8 text-xs font-mono bg-muted/50"
              />
            </div>
            <div>
              <Label className="text-xs text-muted-foreground mb-1 block">Longitude</Label>
              <Input
                type="number"
                step="0.00001"
                placeholder="34.780"
                value={pendingCoord?.lng ?? ''}
                onChange={e => {
                  const lng = parseFloat(e.target.value);
                  if (!isNaN(lng)) onCoordChange({ lat: pendingCoord?.lat ?? 0, lng });
                }}
                className="h-8 text-xs font-mono bg-muted/50"
              />
            </div>
          </div>

          {/* Map-click placement toggle */}
          <button
            onClick={onTogglePlacement}
            className={cn(
              'w-full flex items-center justify-center gap-2 px-3 py-2 rounded-xl border text-xs font-medium transition-all',
              placementMode
                ? 'bg-primary/10 border-primary text-primary animate-pulse'
                : 'border-border text-muted-foreground hover:bg-muted/40'
            )}
          >
            <Crosshair className="h-3.5 w-3.5" />
            {placementMode ? 'Click map to place...' : 'Pick from Map'}
          </button>

          {pendingCoord && (
            <div className="flex items-center justify-between px-3 py-2 rounded-xl bg-green-500/10 border border-green-500/20 text-xs">
              <span className="text-green-400 font-mono">
                {pendingCoord.lat.toFixed(5)}, {pendingCoord.lng.toFixed(5)}
              </span>
              <button onClick={onClearCoord} className="text-muted-foreground hover:text-foreground ml-2">
                <X className="h-3 w-3" />
              </button>
            </div>
          )}
        </div>

        {/* Place button */}
        <Button
          className="w-full font-semibold"
          onClick={onPlace}
          disabled={!pendingCoord || isPlacing}
          style={{ background: 'linear-gradient(135deg, hsl(0,84%,55%), hsl(0,84%,42%))' }}
        >
          {isPlacing ? 'Placing...' : `Place ${selectedEntity.emoji} ${entityType}`}
        </Button>

        <p className="text-xs text-center text-muted-foreground">
          Activate "Pick from Map" then click the map on the left
        </p>
      </div>
    </motion.div>
  );
}
