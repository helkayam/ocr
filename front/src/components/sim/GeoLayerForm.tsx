/**
 * GeoLayerForm — shared category selector + file-pick button for GeoJSON uploads.
 * Used by UploadLayerModal (MapView) and the "Upload Map" tab in WorkspaceDetails.
 */
import { useRef } from 'react';
import { Upload } from 'lucide-react';
import { cn } from '@/lib/utils';

export type GeoCategory = 'cameras' | 'shelters' | 'buildings';

export const GEO_CATEGORIES: { type: GeoCategory; emoji: string; label: string; desc: string }[] = [
  { type: 'shelters',  emoji: '🏠', label: 'Shelters',  desc: 'Emergency shelter points' },
  { type: 'cameras',   emoji: '📷', label: 'Cameras',   desc: 'Surveillance camera points' },
  { type: 'buildings', emoji: '🏢', label: 'Buildings', desc: 'Building polygon layer' },
];

interface GeoLayerFormProps {
  geoCategory: GeoCategory;
  onGeoCategoryChange: (cat: GeoCategory) => void;
  /** Called with the selected File. Modal close (if any) is the caller's responsibility. */
  onFileSelect: (file: File) => void;
  isUploading: boolean;
  uploadProgress: string | null;
}

export function GeoLayerForm({
  geoCategory,
  onGeoCategoryChange,
  onFileSelect,
  isUploading,
  uploadProgress,
}: GeoLayerFormProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <div className="space-y-4">
      {/* Category radio buttons */}
      <div className="space-y-2">
        <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
          Layer Category
        </p>
        <div className="space-y-2">
          {GEO_CATEGORIES.map(cat => (
            <button
              key={cat.type}
              onClick={() => onGeoCategoryChange(cat.type)}
              className={cn(
                'w-full flex items-center gap-3 px-3 py-2.5 rounded-xl border text-left transition-all',
                geoCategory === cat.type
                  ? 'bg-primary/10 border-primary text-primary'
                  : 'border-border text-foreground hover:bg-muted/40'
              )}
            >
              <span className="text-xl shrink-0">{cat.emoji}</span>
              <div>
                <p className="text-sm font-semibold">{cat.label}</p>
                <p className="text-xs text-muted-foreground">{cat.desc}</p>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* File pick */}
      <input
        ref={fileInputRef}
        type="file"
        accept=".geojson,.json"
        className="hidden"
        onChange={e => {
          const file = e.target.files?.[0];
          if (file) onFileSelect(file);
          e.target.value = '';
        }}
      />
      <button
        onClick={() => fileInputRef.current?.click()}
        disabled={isUploading}
        className={cn(
          'w-full flex flex-col items-center gap-3 py-6 rounded-2xl border-2 border-dashed transition-all',
          isUploading
            ? 'border-primary/30 bg-primary/5 cursor-not-allowed'
            : 'border-border hover:border-primary/40 hover:bg-muted/30 cursor-pointer'
        )}
      >
        <div className="p-3 rounded-2xl bg-muted">
          <Upload className={cn('h-5 w-5', isUploading ? 'text-primary animate-bounce' : 'text-muted-foreground')} />
        </div>
        <div className="text-center">
          <p className="text-sm font-semibold">
            {uploadProgress ?? 'Choose .geojson file'}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">GeoJSON or JSON format</p>
        </div>
      </button>
    </div>
  );
}
