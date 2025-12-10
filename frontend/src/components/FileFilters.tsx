import { FileType } from '@/types/files';
import { cn } from '@/lib/utils';
import { FileText, FileType2, Map, Layers, Filter } from 'lucide-react';

interface FileFiltersProps {
  selectedTypes: FileType[];
  onTypeToggle: (type: FileType) => void;
  onClearFilters: () => void;
}

const filterOptions: { type: FileType; label: string; icon: typeof FileText; colorClass: string }[] = [
  { type: 'pdf', label: 'PDF', icon: FileText, colorClass: 'text-red-500 border-red-500/30 bg-red-500/10 hover:bg-red-500/20' },
  { type: 'docx', label: 'DOCX', icon: FileType2, colorClass: 'text-blue-500 border-blue-500/30 bg-blue-500/10 hover:bg-blue-500/20' },
  { type: 'geojson', label: 'GeoJSON', icon: Map, colorClass: 'text-green-500 border-green-500/30 bg-green-500/10 hover:bg-green-500/20' },
  { type: 'shapefile', label: 'Shapefile', icon: Layers, colorClass: 'text-orange-500 border-orange-500/30 bg-orange-500/10 hover:bg-orange-500/20' },
];

export function FileFilters({ selectedTypes, onTypeToggle, onClearFilters }: FileFiltersProps) {
  return (
    <div className="flex items-center gap-3 flex-wrap">
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <Filter className="h-4 w-4" />
        <span>Filter:</span>
      </div>
      
      <div className="flex flex-wrap gap-2">
        {filterOptions.map(({ type, label, icon: Icon, colorClass }) => {
          const isSelected = selectedTypes.includes(type);
          
          return (
            <button
              key={type}
              onClick={() => onTypeToggle(type)}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all duration-200 border',
                isSelected
                  ? colorClass
                  : 'text-muted-foreground border-border bg-muted/30 hover:bg-muted/50'
              )}
            >
              <Icon className="h-3.5 w-3.5" />
              {label}
            </button>
          );
        })}
      </div>

      {selectedTypes.length > 0 && (
        <button
          onClick={onClearFilters}
          className="text-xs text-muted-foreground hover:text-foreground transition-colors underline underline-offset-2"
        >
          Clear all
        </button>
      )}
    </div>
  );
}
