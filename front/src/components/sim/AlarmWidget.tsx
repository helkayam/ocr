/**
 * AlarmWidget — Corner badge that pulses when a simulation is active.
 * Clicking it reopens the Simulation Overlay.
 */
import { motion } from 'framer-motion';
import { Zap, AlertTriangle, X } from 'lucide-react';
import { cn } from '@/lib/utils';
import { EmergencySimResult, Sensor } from '@/types/files';

interface AlarmWidgetProps {
  sensor: Sensor | null;
  result: EmergencySimResult | null;
  isLoading: boolean;
  onClick: () => void;
  onClear: () => void;
}

const URGENCY_STYLES = {
  critical: 'from-red-600 to-red-800 border-red-400/50',
  high:     'from-orange-500 to-orange-700 border-orange-400/50',
  medium:   'from-yellow-500 to-yellow-700 border-yellow-400/50',
  low:      'from-green-500 to-green-700 border-green-400/50',
};

export function AlarmWidget({ sensor, result, isLoading, onClick, onClear }: AlarmWidgetProps) {
  const urgency = result?.alert_level ?? 'high';
  const gradientClass = URGENCY_STYLES[urgency as keyof typeof URGENCY_STYLES] ?? URGENCY_STYLES.high;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.85 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      exit={{ opacity: 0, y: 20, scale: 0.85 }}
      transition={{ type: 'spring', stiffness: 380, damping: 26 }}
      className={cn(
        'absolute bottom-6 left-6 z-[800] flex items-center rounded-2xl overflow-hidden',
        'bg-gradient-to-r border backdrop-blur-sm shadow-2xl text-white',
        gradientClass,
        isLoading && 'animate-pulse'
      )}
      style={{ boxShadow: urgency === 'critical' ? '0 8px 32px rgba(239,68,68,0.5)' : '0 8px 24px rgba(0,0,0,0.4)' }}
    >
      {/* Main clickable area — reopens simulation panel */}
      <button
        onClick={onClick}
        className="flex items-center gap-3 px-4 py-3 hover:brightness-110 transition-all"
      >
        <span className="relative flex h-3 w-3 shrink-0">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-white opacity-75" />
          <span className="relative inline-flex rounded-full h-3 w-3 bg-white" />
        </span>

        <div className="text-left min-w-0">
          <p className="text-xs font-bold uppercase tracking-wider opacity-80">
            {isLoading ? 'Simulating...' : `${urgency.toUpperCase()} Alert`}
          </p>
          {sensor && (
            <p className="text-sm font-semibold truncate max-w-[160px]">{sensor.name}</p>
          )}
        </div>

        <div className="shrink-0 p-1.5 rounded-xl bg-white/20">
          {isLoading
            ? <Zap className="h-4 w-4 animate-bounce" />
            : <AlertTriangle className="h-4 w-4" />
          }
        </div>
      </button>

      {/* Clear button — dismisses simulation entirely */}
      {!isLoading && (
        <button
          onClick={onClear}
          title="Clear simulation"
          className="px-3 py-3 border-l border-white/20 hover:bg-black/20 transition-colors shrink-0 self-stretch flex items-center"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </motion.div>
  );
}
