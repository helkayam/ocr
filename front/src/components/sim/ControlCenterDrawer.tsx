/**
 * ControlCenterDrawer — Sliding panel for sensor and GIS layer management.
 */
import { motion } from 'framer-motion';
import { X, Cpu, Layers, Trash2, Zap, Navigation, ChevronDown } from 'lucide-react';
import { useState } from 'react';
import { cn } from '@/lib/utils';
import { Sensor, GeoFeature, MapLayer } from '@/types/files';
import { LAYER_COLORS } from '@/components/MapComponent';

interface ControlCenterDrawerProps {
  sensors: Sensor[];
  layers: MapLayer[];
  geoFeatures: GeoFeature[];
  selectedLayerIdx: number | null;
  onSelectLayer: (idx: number) => void;
  onDeleteSensor: (id: string) => void;
  onSimulateSensor: (sensor: Sensor) => void;
  onFlyToSensor: (sensor: Sensor) => void;
  onDeleteFeature: (id: string) => void;
  onClose: () => void;
}

const SENSOR_META: Record<string, { emoji: string; label: string; color: string }> = {
  SIREN:     { emoji: '🚨', label: 'Missile Alarm',         color: 'text-red-400' },
  TERRORIST: { emoji: '⚠️', label: 'Terrorist Infiltration', color: 'text-purple-400' },
  HAZMAT:    { emoji: '☢️', label: 'Hazardous Materials',    color: 'text-orange-400' },
};

const GEO_META: Record<string, { emoji: string }> = {
  shelter:      { emoji: '🛡️' },
  exit:         { emoji: '🚪' },
  muster_point: { emoji: '👥' },
  extinguisher: { emoji: '🧯' },
  assembly:     { emoji: '📍' },
  camera:       { emoji: '📷' },
  building:     { emoji: '🏢' },
};

function Section({ title, icon: Icon, count, children }: {
  title: string;
  icon: React.ElementType;
  count: number;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(true);
  return (
    <div className="border-b border-border last:border-0">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-4 py-3 hover:bg-muted/30 transition-colors text-left"
      >
        <Icon className="h-4 w-4 text-primary shrink-0" />
        <span className="text-sm font-semibold flex-1">{title}</span>
        <span className="text-xs text-muted-foreground bg-muted px-2 py-0.5 rounded-full">{count}</span>
        <ChevronDown className={cn('h-3.5 w-3.5 text-muted-foreground transition-transform', open && 'rotate-180')} />
      </button>
      {open && <div className="pb-2">{children}</div>}
    </div>
  );
}

export function ControlCenterDrawer({
  sensors,
  layers,
  geoFeatures,
  selectedLayerIdx,
  onSelectLayer,
  onDeleteSensor,
  onSimulateSensor,
  onFlyToSensor,
  onDeleteFeature,
  onClose,
}: ControlCenterDrawerProps) {
  return (
    <motion.div
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', stiffness: 340, damping: 36 }}
      className="absolute top-0 right-0 bottom-0 w-full sm:w-[360px] z-[800] flex flex-col bg-card/95 backdrop-blur-xl border-l border-border overflow-hidden"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-border bg-background/60 shrink-0">
        <h2 className="text-sm font-bold uppercase tracking-wider flex items-center gap-2">
          <Cpu className="h-4 w-4 text-primary" />
          Control Center
        </h2>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-muted transition-colors text-muted-foreground hover:text-foreground"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      <div className="flex-1 overflow-y-auto">
        {/* Sensors */}
        <Section title="Sensors" icon={Cpu} count={sensors.length}>
          {sensors.length === 0 ? (
            <p className="px-4 py-3 text-xs text-muted-foreground italic">No sensors placed yet.</p>
          ) : (
            <ul className="px-3 space-y-1">
              {sensors.map(s => {
                const meta = SENSOR_META[s.sensor_type] ?? SENSOR_META.SIREN;
                return (
                  <li key={s.sensor_id}
                    className="flex items-center gap-2 p-2 rounded-xl hover:bg-muted/40 transition-colors group"
                  >
                    <span className="text-lg shrink-0">{meta.emoji}</span>
                    <button
                      className="min-w-0 flex-1 text-left"
                      onClick={() => onFlyToSensor(s)}
                      title="Pan to sensor"
                    >
                      <p className="text-xs font-semibold truncate hover:text-primary transition-colors">{s.name}</p>
                      <p className={cn('text-xs', meta.color)}>{meta.label}</p>
                    </button>
                    <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                      <button
                        onClick={() => onSimulateSensor(s)}
                        className="p-1.5 rounded-lg hover:bg-orange-500/15 text-muted-foreground hover:text-orange-400 transition-colors"
                        title="Simulate alert"
                      >
                        <Zap className="h-3.5 w-3.5" />
                      </button>
                      <button
                        onClick={() => onDeleteSensor(s.sensor_id)}
                        className="p-1.5 rounded-lg hover:bg-destructive/15 text-muted-foreground hover:text-destructive transition-colors"
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </Section>

        {/* Geo Features */}
        <Section title="Geo Features" icon={Navigation} count={geoFeatures.length}>
          {geoFeatures.length === 0 ? (
            <p className="px-4 py-3 text-xs text-muted-foreground italic">No features placed yet.</p>
          ) : (
            <ul className="px-3 space-y-1">
              {geoFeatures.map(f => {
                const meta = GEO_META[f.feature_type] ?? { emoji: '📍' };
                return (
                  <li key={f.feature_id}
                    className="flex items-center gap-2 p-2 rounded-xl hover:bg-muted/40 transition-colors group"
                  >
                    <span className="text-lg shrink-0">{meta.emoji}</span>
                    <div className="min-w-0 flex-1">
                      <p className="text-xs font-semibold truncate">{f.label}</p>
                      <p className="text-xs text-muted-foreground capitalize">{f.feature_type.replace('_', ' ')}</p>
                    </div>
                    <button
                      onClick={() => onDeleteFeature(f.feature_id)}
                      className="p-1.5 rounded-lg hover:bg-destructive/15 text-muted-foreground hover:text-destructive transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  </li>
                );
              })}
            </ul>
          )}
        </Section>

        {/* GIS Layers */}
        <Section title="GIS Layers" icon={Layers} count={layers.length}>
          {layers.length === 0 ? (
            <p className="px-4 py-3 text-xs text-muted-foreground italic">No GIS layers loaded.</p>
          ) : (
            <ul className="px-3 space-y-1">
              {layers.map((layer, i) => (
                <li key={layer.layer_id}>
                  <button
                    onClick={() => onSelectLayer(i)}
                    className={cn(
                      'w-full flex items-center gap-2 px-2 py-2 rounded-xl transition-colors text-left',
                      selectedLayerIdx === i
                        ? 'bg-primary/10 text-primary'
                        : 'hover:bg-muted/50 text-foreground'
                    )}
                  >
                    <div className="w-3 h-3 rounded-full shrink-0" style={{ background: LAYER_COLORS[i % LAYER_COLORS.length] }} />
                    <span className="text-xs truncate flex-1">{layer.filename}</span>
                    <span className="text-xs text-muted-foreground shrink-0">{layer.feature_count}</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </Section>
      </div>
    </motion.div>
  );
}
