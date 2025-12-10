import { useCallback, useState } from 'react';
import { Upload, FileUp, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';
import { FileType, UploadQueueItem } from '@/types/files';
import { toast } from 'sonner';

interface FileUploadAreaProps {
  onFilesSelected: (files: File[]) => void;
  isUploading?: boolean;
}

const ACCEPTED_TYPES: Record<string, FileType> = {
  'application/pdf': 'pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
  'application/geo+json': 'geojson',
  'application/json': 'geojson',
  '.shp': 'shapefile',
  '.dbf': 'shapefile',
  '.shx': 'shapefile',
  '.prj': 'shapefile',
};

export function FileUploadArea({ onFilesSelected, isUploading }: FileUploadAreaProps) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const validateFiles = (files: File[]): File[] => {
    const validFiles: File[] = [];
    
    files.forEach(file => {
      const extension = '.' + file.name.split('.').pop()?.toLowerCase();
      const isValidType = ACCEPTED_TYPES[file.type] || ACCEPTED_TYPES[extension];
      
      if (isValidType) {
        validFiles.push(file);
      } else {
        toast.error(`Invalid file type: ${file.name}`, {
          description: 'Supported formats: PDF, DOCX, GeoJSON, Shapefile',
        });
      }
    });

    return validFiles;
  };

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);

    const droppedFiles = Array.from(e.dataTransfer.files);
    const validFiles = validateFiles(droppedFiles);
    
    if (validFiles.length > 0) {
      onFilesSelected(validFiles);
    }
  }, [onFilesSelected]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    const validFiles = validateFiles(selectedFiles);
    
    if (validFiles.length > 0) {
      onFilesSelected(validFiles);
    }
    
    e.target.value = '';
  }, [onFilesSelected]);

  return (
    <div
      className={cn(
        'relative group rounded-xl border-2 border-dashed transition-all duration-300',
        'bg-card/50 hover:bg-card/80',
        isDragging ? 'dropzone-active border-primary' : 'border-primary/40 hover:border-primary/70',
        isUploading && 'pointer-events-none opacity-60'
      )}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      <label className="flex flex-col items-center justify-center py-12 px-8 cursor-pointer">
        <input
          type="file"
          multiple
          className="hidden"
          accept=".pdf,.docx,.geojson,.json,.shp,.dbf,.shx,.prj"
          onChange={handleFileInput}
          disabled={isUploading}
        />
        
        <div className={cn(
          'relative mb-6 p-6 rounded-full transition-all duration-300',
          'bg-primary/10 group-hover:bg-primary/20',
          isDragging && 'scale-110 bg-primary/30'
        )}>
          {isDragging ? (
            <FileUp className="h-12 w-12 text-primary animate-bounce" />
          ) : (
            <Upload className="h-12 w-12 text-primary transition-transform group-hover:scale-110" />
          )}
          
          {/* Glow effect */}
          <div className={cn(
            'absolute inset-0 rounded-full transition-opacity duration-300',
            'bg-primary/20 blur-xl',
            isDragging ? 'opacity-100' : 'opacity-0 group-hover:opacity-50'
          )} />
        </div>

        <h3 className="text-lg font-semibold text-foreground mb-2">
          {isDragging ? 'Drop files here' : 'Drag files here'}
        </h3>
        
        <p className="text-sm text-muted-foreground text-center mb-4">
          PDF / DOCX / GeoJSON / Shapefile
        </p>

        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span className="px-3 py-1.5 rounded-full bg-muted/50 border border-border">
            or click to browse
          </span>
        </div>

        <div className="flex flex-wrap justify-center gap-2 mt-6">
          <span className="px-2 py-1 text-xs rounded bg-red-500/20 text-red-400 border border-red-500/30">PDF</span>
          <span className="px-2 py-1 text-xs rounded bg-blue-500/20 text-blue-400 border border-blue-500/30">DOCX</span>
          <span className="px-2 py-1 text-xs rounded bg-green-500/20 text-green-400 border border-green-500/30">GeoJSON</span>
          <span className="px-2 py-1 text-xs rounded bg-orange-500/20 text-orange-400 border border-orange-500/30">SHP</span>
        </div>
      </label>
    </div>
  );
}
