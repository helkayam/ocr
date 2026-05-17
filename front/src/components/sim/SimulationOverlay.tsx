/**
 * SimulationOverlay — Right-side panel for the two-step emergency simulation flow.
 *
 * Phases (in order):
 *   picker → origin (user clicks map) → loading (Three.js alarm) → result
 *
 * The "Run Simulation" button is locked until `userEvacOrigin` is populated,
 * making user-origin selection a strict prerequisite for triggering the API.
 */
import { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  X, Zap, CheckCircle, MapPin, Navigation,
  ChevronDown, ChevronUp, Cpu, Crosshair,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { Sensor, EmergencySimResult } from '@/types/files';
import { ThreeJSAlarm } from './ThreeJSAlarm';

type Urgency = 'low' | 'medium' | 'high' | 'critical';

interface SimulationOverlayProps {
  sensors: Sensor[];
  simSensor: Sensor | null;
  simResult: EmergencySimResult | null;
  isLoading: boolean;
  userEvacOrigin: { lat: number; lng: number } | null;
  onSelectSensor: (sensor: Sensor) => void;
  onRunSimulation: () => void;
  onResetSensor: () => void;
  onClearSimulation: () => void;
  onClose: () => void;
  onFlyToFeature?: (lat: number, lng: number) => void;
}

const SENSOR_META: Record<string, { emoji: string; label: string; color: string }> = {
  SIREN:     { emoji: '🚨', label: 'אזעקת ירי רקטי',  color: 'text-red-500' },
  TERRORIST: { emoji: '⚠️', label: 'חדירת מחבלים',     color: 'text-purple-500' },
  HAZMAT:    { emoji: '☢️', label: 'חומרים מסוכנים',    color: 'text-orange-500' },
};

const ACTION_HE: Record<string, string> = {
  proceed_to_shelter: 'פינוי מיידי למרחב מוגן',
  evacuate:           'פינוי אזור',
  shelter_in_place:   'הסתתרות במקום',
  alert:              'התרעה',
};

const TARGET_HE: Record<string, string> = {
  shelter:      'מרחב מוגן',
  exit:         'יציאת חירום',
  muster_point: 'נקודת כינוס',
  assembly:     'אזור התכנסות',
  none:         'כללי',
};

const URGENCY_CFG: Record<Urgency, { label: string; headerBg: string; badge: string; glow: string }> = {
  critical: { label: 'דחיפות עליונה', headerBg: 'from-red-950/95 to-red-900/95',       badge: 'bg-red-500/20 text-red-200 border-red-500/30',         glow: 'shadow-[0_0_40px_rgba(239,68,68,0.35)]' },
  high:     { label: 'דחיפות גבוהה',  headerBg: 'from-orange-950/95 to-orange-900/95', badge: 'bg-orange-500/20 text-orange-200 border-orange-500/30', glow: 'shadow-[0_0_30px_rgba(249,115,22,0.3)]' },
  medium:   { label: 'דחיפות בינונית',headerBg: 'from-yellow-950/95 to-yellow-900/95', badge: 'bg-yellow-500/20 text-yellow-200 border-yellow-500/30', glow: 'shadow-[0_0_24px_rgba(234,179,8,0.25)]' },
  low:      { label: 'דחיפות נמוכה',  headerBg: 'from-slate-900/95 to-slate-800/95',   badge: 'bg-slate-500/20 text-slate-200 border-slate-500/30',   glow: '' },
};

const LOADING_STAGES = [
  'מתחבר לרשת החיישנים...',
  'קורא פרוטוקולי חירום...',
  'מנתח פעולות נדרשות...',
  'מחשב מסלולי פינוי...',
];

// ─── Phase views ──────────────────────────────────────────────────────────────

function SensorPickerView({ sensors, onSelect }: { sensors: Sensor[]; onSelect: (s: Sensor) => void }) {
  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-3" dir="rtl">
      <div className="text-center py-4 space-y-1">
        <div className="text-4xl mb-2">🚨</div>
        <p className="font-bold text-base text-slate-900">בחר חיישן</p>
        <p className="text-xs text-slate-500">בחר איזה חיישן להפעיל בסימולציה זו</p>
      </div>

      {sensors.length === 0 ? (
        <div className="text-center py-8 space-y-2">
          <Cpu className="h-10 w-10 mx-auto text-slate-300" />
          <p className="text-sm text-slate-500">אין חיישנים.</p>
          <p className="text-xs text-slate-400">השתמש בכפתור + ישות להצבת חיישנים על המפה.</p>
        </div>
      ) : (
        <ul className="space-y-2">
          {sensors.map(s => {
            const meta = SENSOR_META[s.sensor_type] ?? SENSOR_META.SIREN;
            return (
              <motion.li key={s.sensor_id} whileHover={{ x: -2 }} whileTap={{ scale: 0.98 }}>
                <button
                  onClick={() => onSelect(s)}
                  className="w-full flex items-center gap-3 p-3 rounded-lg bg-white border border-slate-200 shadow-sm hover:border-slate-300 hover:shadow transition-all text-right group"
                >
                  <Zap className="h-4 w-4 text-slate-300 group-hover:text-red-500 transition-colors shrink-0" />
                  <div className="min-w-0 flex-1 text-right">
                    <p className="text-sm font-semibold text-slate-900 truncate">{s.name}</p>
                    <p className={cn('text-xs font-medium', meta.color)}>{meta.label}</p>
                    {s.lat != null && s.lng != null && (
                      <p className="text-xs text-slate-400 font-mono mt-0.5">
                        {s.lat.toFixed(4)}, {s.lng.toFixed(4)}
                      </p>
                    )}
                  </div>
                  <span className="text-xl shrink-0">{meta.emoji}</span>
                </button>
              </motion.li>
            );
          })}
        </ul>
      )}
    </div>
  );
}

function OriginPickingView({
  sensor,
  userEvacOrigin,
  onRunSimulation,
  onResetSensor,
}: {
  sensor: Sensor;
  userEvacOrigin: { lat: number; lng: number } | null;
  onRunSimulation: () => void;
  onResetSensor: () => void;
}) {
  const meta = SENSOR_META[sensor.sensor_type] ?? SENSOR_META.SIREN;
  const hasOrigin = userEvacOrigin !== null;

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-4" dir="rtl">

      {/* Staged sensor */}
      <div className="flex items-center gap-3 p-3 rounded-lg bg-white border border-slate-200 shadow-sm">
        <div className="min-w-0 flex-1 text-right">
          <p className="text-sm font-semibold text-slate-900 truncate">{sensor.name}</p>
          <p className={cn('text-xs font-medium', meta.color)}>{meta.label}</p>
        </div>
        <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
        <span className="text-xl shrink-0">{meta.emoji}</span>
      </div>

      {/* Step progress */}
      <div className="flex items-center gap-2 text-xs" dir="ltr">
        <div className="flex items-center gap-1.5">
          <CheckCircle className="h-3.5 w-3.5 text-green-500 shrink-0" />
          <span className="text-green-600 font-medium">חיישן מוכן</span>
        </div>
        <div className="h-px flex-1 bg-slate-200" />
        <div className="flex items-center gap-1.5">
          <div className={cn(
            'h-3.5 w-3.5 rounded-full border-2 shrink-0',
            hasOrigin ? 'border-green-500 bg-green-500' : 'border-blue-400 animate-pulse'
          )} />
          <span className={cn('font-medium', hasOrigin ? 'text-green-600' : 'text-blue-500')}>
            נקודת מוצא
          </span>
        </div>
        <div className="h-px flex-1 bg-slate-200" />
        <div className="flex items-center gap-1.5">
          <div className="h-3.5 w-3.5 rounded-full border-2 border-slate-300 shrink-0" />
          <span className="text-slate-400">הרצה</span>
        </div>
      </div>

      {/* Map click instruction / origin display */}
      <div className={cn(
        'p-4 rounded-lg border-2 border-dashed transition-colors duration-300',
        hasOrigin ? 'border-green-400/60 bg-green-50' : 'border-blue-400/60 bg-blue-50'
      )}>
        {hasOrigin ? (
          <div className="flex items-start gap-2.5 flex-row-reverse">
            <MapPin className="h-4 w-4 text-green-500 shrink-0 mt-0.5" />
            <div className="min-w-0 text-right">
              <p className="text-xs font-semibold text-green-700 mb-0.5">נקודת מוצא נקבעה</p>
              <p className="font-mono text-xs text-slate-700">
                {userEvacOrigin!.lat.toFixed(5)}, {userEvacOrigin!.lng.toFixed(5)}
              </p>
              <p className="text-xs text-slate-500 mt-1">לחץ שוב על המפה לשינוי</p>
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2.5 flex-row-reverse">
            <Crosshair className="h-4 w-4 text-blue-500 shrink-0 mt-0.5 animate-pulse" />
            <div className="text-right">
              <p className="text-xs font-semibold text-slate-800 mb-1">קבע את נקודת המוצא לפינוי</p>
              <p className="text-xs text-slate-500 leading-relaxed">
                לחץ על המפה לבחירת מיקומך הנוכחי.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Actions */}
      <div className="space-y-2 pt-1">
        <button
          onClick={onRunSimulation}
          disabled={!hasOrigin}
          className={cn(
            'w-full py-3 rounded-xl text-sm font-bold transition-all duration-200',
            !hasOrigin && 'bg-slate-100 text-slate-400 cursor-not-allowed'
          )}
          style={hasOrigin ? {
            background: 'linear-gradient(160deg, hsl(0,84%,55%) 0%, hsl(0,84%,38%) 100%)',
            boxShadow: '0 4px 18px rgba(239,68,68,0.45)',
            color: '#fff',
          } : undefined}
        >
          {hasOrigin ? '🚨 הרץ סימולציה' : 'קבע נקודת מוצא להמשך ←'}
        </button>

        <button
          onClick={onResetSensor}
          className="w-full py-2 rounded-xl text-xs text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition-colors"
        >
          ← החלף חיישן
        </button>
      </div>
    </div>
  );
}

function LoadingView({ sensor }: { sensor: Sensor }) {
  const [stageIdx, setStageIdx] = useState(0);
  useEffect(() => {
    setStageIdx(0);
    const delays = [1500, 3200, 5200];
    const timers = delays.map((d, i) => setTimeout(() => setStageIdx(i + 1), d));
    return () => timers.forEach(clearTimeout);
  }, []);
  const meta = SENSOR_META[sensor.sensor_type] ?? SENSOR_META.SIREN;
  return (
    <div className="flex-1 flex flex-col items-center justify-center gap-6 p-8">
      <div className="flex flex-col items-center gap-2">
        <ThreeJSAlarm active size={160} urgency="high" />
        <p className="text-2xl">{meta.emoji}</p>
      </div>
      <div className="text-center space-y-1" dir="rtl">
        <p className="text-sm font-bold text-orange-500 tracking-widest">סימולציה פעילה</p>
        <p className="text-base font-semibold text-slate-900">{sensor.name}</p>
        <p className="text-xs text-slate-500">{meta.label}</p>
      </div>
      <div className="w-full space-y-2" dir="rtl">
        {LOADING_STAGES.map((stage, i) => (
          <motion.div
            key={stage}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: i <= stageIdx ? 1 : 0.25, x: 0 }}
            transition={{ delay: i * 0.05 }}
            className={cn(
              'flex items-center gap-2 text-xs px-3 py-2 rounded-lg',
              i < stageIdx   && 'bg-green-50 text-green-700 border border-green-200',
              i === stageIdx && 'bg-orange-50 text-orange-700 border border-orange-200',
              i > stageIdx   && 'text-slate-400'
            )}
          >
            <span className="flex-1 text-right">{stage}</span>
            {i < stageIdx   && <CheckCircle className="h-3.5 w-3.5 shrink-0" />}
            {i === stageIdx && <span className="h-3.5 w-3.5 shrink-0 animate-spin inline-block border-2 border-orange-400 border-t-transparent rounded-full" />}
            {i > stageIdx   && <span className="h-3.5 w-3.5 shrink-0 rounded-full border border-slate-300" />}
          </motion.div>
        ))}
      </div>
    </div>
  );
}

function ResultView({
  result,
  onClearSimulation,
  onFlyToFeature,
}: {
  result: EmergencySimResult;
  onClearSimulation: () => void;
  onFlyToFeature?: (lat: number, lng: number) => void;
}) {
  const [showRag, setShowRag] = useState(true);
  const urgency = (result.alert_level ?? result.intent.urgency) as Urgency;
  const cfg = URGENCY_CFG[urgency] ?? URGENCY_CFG.high;
  const meta = SENSOR_META[result.sensor.sensor_type] ?? SENSOR_META.SIREN;
  const isNonSpatial = result.intent.target_type === 'none';
  const hasGeoResult = result.nearest_feature !== null;

  const actionLabel = ACTION_HE[result.intent.action] ?? result.intent.action;
  const targetLabel = TARGET_HE[result.intent.target_type] ?? result.intent.target_type;

  return (
    <div className="flex-1 overflow-y-auto">

      {/* Urgency header */}
      <div className={cn('px-5 py-4 bg-gradient-to-r', cfg.headerBg)}>
        <div className="flex items-center gap-3" dir="rtl">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className={cn('text-xs font-bold px-2.5 py-0.5 rounded-full border', cfg.badge)}>
                {cfg.label}
              </span>
              <span className="text-xs text-slate-300">{meta.label}</span>
            </div>
            <p className="text-base font-bold text-white">{result.sensor.name}</p>
          </div>
          <ThreeJSAlarm active={urgency === 'critical' || urgency === 'high'} urgency={urgency} size={64} />
        </div>
      </div>

      <div className="p-4 space-y-3">

        {/* סיווג האירוע */}
        <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-sm space-y-2" dir="rtl">
          <p className="text-xs font-semibold text-slate-500 tracking-wide">סיווג האירוע</p>
          <div className="flex flex-wrap gap-1.5">
            <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-800 border border-slate-200 font-medium">
              {actionLabel}
            </span>
            {!isNonSpatial && (
              <span className="text-xs px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 border border-slate-200 font-medium">
                ← {targetLabel}
              </span>
            )}
          </div>
        </div>

        {/* מרחב מוגן קרוב ביותר */}
        {!isNonSpatial && (
          hasGeoResult ? (() => {
            const nf = result.nearest_feature!;
            const canFly = onFlyToFeature != null;
            return (
              <div
                dir="rtl"
                onClick={canFly ? () => onFlyToFeature(nf.lat, nf.lng) : undefined}
                className={cn(
                  'p-3 rounded-lg bg-white border border-slate-200 shadow-sm space-y-2',
                  canFly && 'cursor-pointer hover:border-blue-300 hover:shadow-md transition-all group'
                )}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500 shrink-0" />
                    <p className="text-xs font-semibold text-slate-700">
                      {TARGET_HE[nf.feature_type] ?? nf.feature_type} קרוב ביותר
                    </p>
                  </div>
                  {canFly && (
                    <span className="text-xs text-blue-500 opacity-0 group-hover:opacity-100 transition-opacity shrink-0 flex items-center gap-1">
                      <Navigation className="h-3 w-3" />
                      מיקום במפה
                    </span>
                  )}
                </div>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-base font-bold text-slate-900 shrink-0">
                    {nf.distance_display ?? `${nf.distance_m} מ'`}
                  </span>
                  <div className="flex items-center gap-1.5 min-w-0">
                    {nf.floor && (
                      <span className="text-xs text-slate-400 shrink-0">({nf.floor})</span>
                    )}
                    <span className="text-sm font-medium text-slate-900 truncate">{nf.label}</span>
                    <MapPin className={cn('h-3.5 w-3.5 shrink-0', canFly ? 'text-blue-400 group-hover:text-blue-600 transition-colors' : 'text-slate-400')} />
                  </div>
                </div>
              </div>
            );
          })()
          : (
            <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-sm flex items-start gap-2" dir="rtl">
              <p className="text-xs text-slate-600 leading-relaxed flex-1">
                לא נמצא <span className="font-medium">{targetLabel}</span> רשום — פעל לפי פרוטוקול פינוי כללי.
              </p>
              <Navigation className="h-4 w-4 text-slate-400 shrink-0 mt-0.5" />
            </div>
          )
        )}

        {/* מקור הפרוטוקול */}
        <div className="rounded-lg bg-white border border-slate-200 shadow-sm overflow-hidden">
          <button
            onClick={() => setShowRag(!showRag)}
            className="w-full flex items-center justify-between px-3 py-2.5 text-xs hover:bg-slate-50 transition-colors"
            dir="rtl"
          >
            <span className="font-semibold text-slate-700">מקור הפרוטוקול</span>
            {showRag ? <ChevronUp className="h-3.5 w-3.5 text-slate-400" /> : <ChevronDown className="h-3.5 w-3.5 text-slate-400" />}
          </button>
          <AnimatePresence>
            {showRag && (
              <motion.div
                initial={{ height: 0 }}
                animate={{ height: 'auto' }}
                exit={{ height: 0 }}
                className="overflow-hidden"
              >
                <div
                  dir="rtl"
                  className="px-4 pb-4 pt-2 text-sm text-slate-800 leading-relaxed border-t border-slate-100 text-right overflow-y-auto max-h-80 whitespace-pre-wrap"
                >
                  {result.rag_answer}
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>

        {/* Clear simulation */}
        <button
          onClick={onClearSimulation}
          className="w-full flex items-center justify-center gap-2 py-2.5 rounded-xl text-xs font-semibold text-slate-500 hover:text-slate-800 hover:bg-slate-200 border border-slate-200 transition-all"
        >
          <X className="h-3.5 w-3.5" />
          נקה סימולציה
        </button>

      </div>
    </div>
  );
}

// ─── Shell ────────────────────────────────────────────────────────────────────

export function SimulationOverlay({
  sensors,
  simSensor,
  simResult,
  isLoading,
  userEvacOrigin,
  onSelectSensor,
  onRunSimulation,
  onResetSensor,
  onClearSimulation,
  onClose,
  onFlyToFeature,
}: SimulationOverlayProps) {
  const urgency = (simResult?.alert_level ?? simResult?.intent?.urgency ?? 'high') as keyof typeof URGENCY_CFG;
  const cfg = URGENCY_CFG[urgency] ?? URGENCY_CFG.high;

  const phase =
    isLoading   ? 'loading'
    : simResult  ? 'result'
    : simSensor  ? 'origin'
    :              'picker';

  const headerTitle =
    phase === 'loading' ? 'סימולציה פעילה'
    : phase === 'result'  ? 'תוצאות הסימולציה'
    : phase === 'origin'  ? 'קביעת נקודת מוצא'
    :                       'סימולציית חירום';

  return (
    <motion.div
      initial={{ x: '100%', opacity: 0 }}
      animate={{ x: 0, opacity: 1 }}
      exit={{ x: '100%', opacity: 0 }}
      transition={{ type: 'spring', stiffness: 340, damping: 36 }}
      className={cn(
        'absolute top-0 right-0 bottom-0 w-full sm:w-[420px] z-[800]',
        'flex flex-col bg-slate-50/95 backdrop-blur-xl border-l border-slate-200 overflow-hidden',
        phase === 'result' && cfg.glow,
      )}
    >
      {/* Header */}
      <div
        className="flex items-center justify-between px-5 py-4 border-b border-slate-200 bg-white/80 shrink-0"
        dir="rtl"
      >
        <div className="flex items-center gap-2">
          <div className="relative">
            <span className="animate-ping absolute inline-flex h-3 w-3 rounded-full bg-red-400 opacity-70" />
            <span className="relative inline-flex rounded-full h-3 w-3 bg-red-500" />
          </div>
          <h2 className="text-sm font-bold tracking-wide text-slate-900">{headerTitle}</h2>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors text-slate-400 hover:text-slate-700"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Phase content */}
      <AnimatePresence mode="wait">
        {phase === 'loading' && simSensor ? (
          <motion.div key="loading" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="flex-1 flex flex-col">
            <LoadingView sensor={simSensor} />
          </motion.div>
        ) : phase === 'result' && simResult ? (
          <motion.div key="result" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex-1 flex flex-col">
            <ResultView result={simResult} onClearSimulation={onClearSimulation} onFlyToFeature={onFlyToFeature} />
          </motion.div>
        ) : phase === 'origin' && simSensor ? (
          <motion.div key="origin" initial={{ opacity: 0, x: -10 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 10 }} className="flex-1 flex flex-col">
            <OriginPickingView
              sensor={simSensor}
              userEvacOrigin={userEvacOrigin}
              onRunSimulation={onRunSimulation}
              onResetSensor={onResetSensor}
            />
          </motion.div>
        ) : (
          <motion.div key="picker" initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex-1 flex flex-col">
            <SensorPickerView sensors={sensors} onSelect={onSelectSensor} />
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
