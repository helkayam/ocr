import { useCallback, useState } from 'react';
import { Upload, FileUp } from 'lucide-react';
import { cn } from '@/lib/utils';
import { FileType } from '@/types/files';
import { toast } from 'sonner';
import { motion } from 'framer-motion';

interface FileUploadAreaProps {
  onFilesSelected: (files: File[]) => void;
  isUploading?: boolean;
}

const ACCEPTED_TYPES: Record<string, FileType> = {
  'application/pdf': 'pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': 'docx',
  'application/geo+json': 'geojson',
  'application/json': 'geojson',
  '.pdf': 'pdf',
  '.docx': 'docx',
  '.geojson': 'geojson',
  '.json': 'geojson',
  '.shp': 'shapefile',
  '.dbf': 'shapefile',
  '.shx': 'shapefile',
  '.prj': 'shapefile',
};

const TYPE_PILLS = [
  { label: 'PDF',     from: 'hsl(0,84%,65%)',   to: 'hsl(20,90%,60%)' },
  { label: 'DOCX',    from: 'hsl(215,90%,62%)', to: 'hsl(199,89%,55%)' },
  { label: 'GeoJSON', from: 'hsl(142,60%,50%)', to: 'hsl(158,64%,48%)' },
  { label: 'SHP',     from: 'hsl(30,90%,60%)',  to: 'hsl(38,92%,55%)' },
];

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
    if (validFiles.length > 0) onFilesSelected(validFiles);
  }, [onFilesSelected]);

  const handleFileInput = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFiles = Array.from(e.target.files || []);
    const validFiles = validateFiles(selectedFiles);
    if (validFiles.length > 0) onFilesSelected(validFiles);
    e.target.value = '';
  }, [onFilesSelected]);

  return (
    <motion.div
      animate={isDragging ? { scale: 1.02 } : { scale: 1 }}
      transition={{ type: 'spring', stiffness: 300, damping: 20 }}
      className={cn(
        'relative rounded-3xl border-2 border-dashed transition-all duration-300',
        isDragging ? 'dropzone-active' : '',
        isUploading && 'pointer-events-none opacity-60'
      )}
      style={!isDragging ? {
        background: 'linear-gradient(135deg, hsl(0,0%,99%) 0%, hsl(0,0%,97%) 100%)',
        borderColor: 'hsla(0,84%,60%,0.35)',
        boxShadow: '0 4px 16px rgba(239,68,68,0.08), inset 0 1px 0 rgba(255,255,255,0.9)',
      } : undefined}
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

        {/* Icon bubble */}
        <motion.div
          animate={isDragging ? { scale: 1.15, rotate: -8 } : { scale: 1, rotate: 0 }}
          transition={{ type: 'spring', stiffness: 300, damping: 18 }}
          className="relative mb-6 p-5 rounded-3xl"
          style={{
            background: isDragging
              ? 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)'
              : 'linear-gradient(135deg, hsl(0,0%,96%) 0%, hsl(0,0%,92%) 100%)',
            boxShadow: isDragging
              ? '0 8px 24px rgba(239,68,68,0.4), inset 0 1px 0 rgba(255,255,255,0.3)'
              : '0 4px 12px rgba(239,68,68,0.10), inset 0 1px 0 rgba(255,255,255,0.9)',
          }}
        >
          {isDragging
            ? <FileUp className="h-11 w-11 text-white" />
            : <Upload className="h-11 w-11" style={{ color: 'hsl(0,84%,58%)' }} />
          }
        </motion.div>

        <h3 className="text-lg font-bold mb-1.5" style={{ color: isDragging ? 'hsl(0,84%,55%)' : 'hsl(0,0%,9%)' }}>
          {isDragging ? 'Drop files here' : 'Drag files here'}
        </h3>

        <p className="text-sm text-muted-foreground text-center mb-5 font-medium">
          PDF · DOCX · GeoJSON · Shapefile
        </p>

        <motion.div
          whileHover={{ scale: 1.04 }}
          whileTap={{ scale: 0.96 }}
          className="px-4 py-2 rounded-2xl text-sm font-semibold text-white mb-6"
          style={{
            background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
            boxShadow: '0 4px 12px rgba(239,68,68,0.32), inset 0 1px 0 rgba(255,255,255,0.25)',
          }}
        >
          or click to browse
        </motion.div>

        {/* Type pills */}
        <div className="flex flex-wrap justify-center gap-2">
          {TYPE_PILLS.map(({ label, from, to }) => (
            <span
              key={label}
              className="px-2.5 py-1 text-xs rounded-xl font-semibold text-white"
              style={{
                background: `linear-gradient(135deg, ${from} 0%, ${to} 100%)`,
                boxShadow: '0 2px 6px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.2)',
              }}
            >
              {label}
            </span>
          ))}
        </div>
      </label>
    </motion.div>
  );
}
