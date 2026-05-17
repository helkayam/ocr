import { useState, useEffect } from 'react';
import { EmergencySimResult } from '@/types/files';
import { AlertTriangle, CheckCircle, MapPin, Zap, Navigation, ChevronDown, ChevronUp } from 'lucide-react';
import { cn } from '@/lib/utils';

interface Props {
  result: EmergencySimResult | null;
  isLoading: boolean;
}

const LOADING_STAGES = [
  'Connecting to sensor...',
  'Reading emergency protocols...',
  'Analyzing required actions...',
  'Calculating evacuation routes...',
];

const URGENCY_CONFIG = {
  low:      { label: 'LOW',      bg: 'bg-green-950/40',  badge: 'bg-green-500/20 text-green-400 border-green-500/30' },
  medium:   { label: 'MEDIUM',   bg: 'bg-yellow-950/40', badge: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30' },
  high:     { label: 'HIGH',     bg: 'bg-orange-950/40', badge: 'bg-orange-500/20 text-orange-400 border-orange-500/30' },
  critical: { label: 'CRITICAL', bg: 'bg-red-950/40',    badge: 'bg-red-500/20 text-red-400 border-red-500/30' },
};

export function EmergencyResultCard({ result, isLoading }: Props) {
  const [stageIndex, setStageIndex] = useState(0);
  const [showRag, setShowRag] = useState(false);

  useEffect(() => {
    if (!isLoading) {
      setStageIndex(0);
      return;
    }
    setStageIndex(0);
    const delays = [1500, 3000, 5000];
    const timers = delays.map((delay, i) => setTimeout(() => setStageIndex(i + 1), delay));
    return () => timers.forEach(clearTimeout);
  }, [isLoading]);

  if (isLoading) {
    return (
      <div className="p-4 rounded-xl bg-card border border-orange-500/30 space-y-3">
        <div className="flex items-center gap-2">
          <span className="relative flex h-2.5 w-2.5">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-orange-400 opacity-75" />
            <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-orange-500" />
          </span>
          <span className="text-sm text-orange-400 font-medium transition-all duration-500">
            {LOADING_STAGES[Math.min(stageIndex, LOADING_STAGES.length - 1)]}
          </span>
        </div>
        <div className="space-y-2 opacity-40">
          {[100, 85, 70, 50].map((w, i) => (
            <div key={i} className={`h-3 rounded bg-muted animate-pulse`} style={{ width: `${w}%` }} />
          ))}
        </div>
      </div>
    );
  }

  if (!result) return null;

  const urgency = result.intent.urgency as keyof typeof URGENCY_CONFIG;
  const cfg = URGENCY_CONFIG[urgency] ?? URGENCY_CONFIG.high;
  const isNonSpatial = result.intent.target_type === 'none';
  const hasGeoResult = result.nearest_feature !== null;

  return (
    <div className="rounded-xl bg-card border border-border overflow-hidden">
      {/* Header */}
      <div className={cn('px-4 py-3 flex items-center gap-2', cfg.bg)}>
        <AlertTriangle className={cn(
          'h-4 w-4',
          urgency === 'critical' ? 'text-red-400' : 'text-orange-400'
        )} />
        <span className="text-sm font-semibold">Simulation Result</span>
      </div>

      <div className="p-4 space-y-3">
        {/* Sensor info */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Zap className="h-3.5 w-3.5 text-yellow-400 shrink-0" />
          <span>
            Triggered by:{' '}
            <span className="font-medium text-foreground">{result.sensor.name}</span>
            {' · '}
            <span>{result.sensor.sensor_type}</span>
          </span>
        </div>

        {/* Extracted intent */}
        <div className="p-3 rounded-lg bg-muted/50 border border-border space-y-2">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
            Extracted Intent
          </p>
          <div className="flex flex-wrap gap-1.5">
            <span className="text-xs px-2 py-0.5 rounded-full bg-blue-500/20 text-blue-400 border border-blue-500/30 font-mono">
              {result.intent.action}
            </span>
            {!isNonSpatial && (
              <span className="text-xs px-2 py-0.5 rounded-full bg-purple-500/20 text-purple-400 border border-purple-500/30 font-mono">
                → {result.intent.target_type}
              </span>
            )}
          </div>
        </div>

        {/* Geo routing result (only if spatial action required) */}
        {!isNonSpatial && (
          hasGeoResult ? (
            <div className="p-3 rounded-lg bg-green-950/30 border border-green-500/20 space-y-1.5">
              <div className="flex items-center gap-1.5">
                <CheckCircle className="h-4 w-4 text-green-400 shrink-0" />
                <p className="text-xs font-semibold text-green-400 capitalize">
                  Nearest {result.nearest_feature!.feature_type.replace('_', ' ')}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-1.5 min-w-0">
                  <MapPin className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
                  <span className="text-sm font-medium truncate">{result.nearest_feature!.label}</span>
                  {result.nearest_feature!.floor && (
                    <span className="text-xs text-muted-foreground shrink-0">
                      ({result.nearest_feature!.floor})
                    </span>
                  )}
                </div>
                <span className="text-sm font-bold text-green-400 shrink-0 ml-2">
                  {result.nearest_feature!.distance_display ??
                    `${result.nearest_feature!.distance_m} m`}
                </span>
              </div>
            </div>
          ) : (
            <div className="p-3 rounded-lg bg-yellow-950/30 border border-yellow-500/20 flex items-start gap-2">
              <Navigation className="h-4 w-4 text-yellow-400 shrink-0 mt-0.5" />
              <p className="text-xs text-yellow-300 leading-relaxed">
                No{' '}
                <span className="font-mono">{result.intent.target_type}</span>{' '}
                feature registered in this workspace — follow general evacuation protocol.
              </p>
            </div>
          )
        )}

        {/* Final directive */}
        <div className="p-3 rounded-lg bg-primary/5 border border-primary/20">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide mb-1.5">
            Directive
          </p>
          <p className="text-xs font-mono font-semibold text-foreground leading-relaxed">
            {result.directive}
          </p>
        </div>

        {/* Hebrew RAG answer (collapsible) */}
        <div className="border border-border rounded-lg overflow-hidden">
          <button
            onClick={() => setShowRag(!showRag)}
            className="w-full flex items-center justify-between px-3 py-2 text-xs text-muted-foreground hover:bg-muted/50 transition-colors"
          >
            <span>Protocol Source (Hebrew)</span>
            {showRag ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}
          </button>
          {showRag && (
            <div
              dir="rtl"
              className="px-3 pb-3 pt-2 text-xs text-foreground/80 leading-relaxed border-t border-border text-right"
            >
              {result.rag_answer}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
