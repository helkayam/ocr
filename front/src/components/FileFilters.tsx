import { FileType } from '@/types/files';
import { cn } from '@/lib/utils';
import { FileText, FileType2, Map, SlidersHorizontal } from 'lucide-react';
import { motion } from 'framer-motion';

interface FileFiltersProps {
  selectedTypes: FileType[];
  onTypeToggle: (type: FileType) => void;
  onClearFilters: () => void;
}

const filterOptions: {
  type: FileType;
  label: string;
  icon: typeof FileText;
  from: string;
  to: string;
  glow: string;
}[] = [
  { type: 'pdf',     label: 'PDF',     icon: FileText,  from: 'hsl(0,84%,65%)',   to: 'hsl(20,90%,60%)',  glow: 'rgba(239,68,68,0.25)' },
  { type: 'docx',    label: 'DOCX',    icon: FileType2, from: 'hsl(215,90%,62%)', to: 'hsl(199,89%,55%)', glow: 'rgba(59,130,246,0.25)' },
  { type: 'geojson', label: 'GeoJSON', icon: Map,       from: 'hsl(142,60%,50%)', to: 'hsl(158,64%,48%)', glow: 'rgba(34,197,94,0.25)' },
];

export function FileFilters({ selectedTypes, onTypeToggle, onClearFilters }: FileFiltersProps) {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex items-center gap-1.5 text-sm text-muted-foreground font-medium">
        <SlidersHorizontal className="h-4 w-4" />
        <span>Filter:</span>
      </div>

      <div className="flex flex-wrap gap-2">
        {filterOptions.map(({ type, label, icon: Icon, from, to, glow }) => {
          const isSelected = selectedTypes.includes(type);
          return (
            <motion.button
              key={type}
              onClick={() => onTypeToggle(type)}
              whileHover={{ scale: 1.06 }}
              whileTap={{ scale: 0.94 }}
              transition={{ type: 'spring', stiffness: 400, damping: 18 }}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-2xl text-xs font-semibold transition-all duration-200 border"
              style={isSelected ? {
                background: `linear-gradient(135deg, ${from} 0%, ${to} 100%)`,
                color: 'white',
                border: '1px solid transparent',
                boxShadow: `0 4px 12px ${glow}, inset 0 1px 0 rgba(255,255,255,0.2)`,
              } : {
                background: 'hsl(0,0%,97%)',
                color: 'hsl(0,0%,45%)',
                borderColor: 'hsl(0,0%,88%)',
                boxShadow: '0 1px 4px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.8)',
              }}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </motion.button>
          );
        })}
      </div>

      {selectedTypes.length > 0 && (
        <motion.button
          initial={{ opacity: 0, scale: 0.8 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.8 }}
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onClearFilters}
          className="text-xs font-semibold px-3 py-1.5 rounded-2xl text-muted-foreground hover:text-foreground transition-colors"
          style={{
            background: 'hsl(0,0%,95%)',
            boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.05)',
          }}
        >
          Clear all
        </motion.button>
      )}
    </div>
  );
}
