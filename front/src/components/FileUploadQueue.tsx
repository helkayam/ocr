import { X, CheckCircle2, AlertCircle, Loader2, CloudUpload } from 'lucide-react';
import { UploadQueueItem, FileType } from '@/types/files';
import { FileTypeIcon } from './FileTypeIcon';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

interface FileUploadQueueProps {
  items: UploadQueueItem[];
  onRemove: (id: string) => void;
}

function getFileType(fileName: string): FileType {
  const ext = fileName.split('.').pop()?.toLowerCase();
  switch (ext) {
    case 'pdf': return 'pdf';
    case 'docx': return 'docx';
    case 'geojson':
    case 'json': return 'geojson';
    default: return 'pdf';
  }
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function FileUploadQueue({ items, onRemove }: FileUploadQueueProps) {
  if (items.length === 0) return null;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
        <div
          className="p-1.5 rounded-xl"
          style={{ background: 'linear-gradient(135deg, hsl(0,84%,55%), hsl(0,84%,42%))' }}
        >
          <CloudUpload className="h-3.5 w-3.5 text-white" />
        </div>
        Upload Queue ({items.length} file{items.length > 1 ? 's' : ''})
      </div>

      <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin pr-1">
        <AnimatePresence initial={false}>
          {items.map((item) => (
            <motion.div
              key={item.id}
              initial={{ opacity: 0, y: 12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, x: 20, scale: 0.95 }}
              transition={{ type: 'spring', stiffness: 350, damping: 26 }}
              className="flex items-center gap-3 p-3.5 rounded-2xl bg-white border border-white/80"
              style={{
                boxShadow: item.status === 'error'
                  ? '0 3px 10px rgba(239,68,68,0.12), inset 0 1px 0 rgba(255,255,255,0.9)'
                  : item.status === 'completed'
                  ? '0 3px 10px rgba(52,211,153,0.12), inset 0 1px 0 rgba(255,255,255,0.9)'
                  : '0 3px 10px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.9)',
                borderColor: item.status === 'error'
                  ? 'hsla(0,84%,65%,0.25)'
                  : item.status === 'completed'
                  ? 'hsla(158,64%,48%,0.25)'
                  : 'rgba(255,255,255,0.8)',
              }}
            >
              <FileTypeIcon type={getFileType(item.file.name)} size="md" />

              <div className="flex-1 min-w-0">
                <div className="flex items-center justify-between mb-1">
                  <p className="text-sm font-semibold truncate pr-4">{item.file.name}</p>
                  <span className="text-xs text-muted-foreground whitespace-nowrap">
                    {formatFileSize(item.file.size)}
                  </span>
                </div>

                {item.status === 'uploading' && (
                  <div className="space-y-1.5">
                    <Progress
                      value={item.progress}
                      className="h-1.5 rounded-full"
                    />
                    <p className="text-xs font-semibold" style={{ color: 'hsl(0,84%,55%)' }}>
                      {item.progress}%
                    </p>
                  </div>
                )}

                {item.status === 'error' && (
                  <p className="text-xs font-medium flex items-center gap-1" style={{ color: 'hsl(0,84%,60%)' }}>
                    <AlertCircle className="h-3 w-3" />
                    {item.error || 'Upload failed'}
                  </p>
                )}

                {item.status === 'completed' && (
                  <p className="text-xs font-medium flex items-center gap-1" style={{ color: 'hsl(158,64%,45%)' }}>
                    <CheckCircle2 className="h-3 w-3" />
                    Uploaded successfully
                  </p>
                )}
              </div>

              <motion.div whileHover={{ scale: 1.1 }} whileTap={{ scale: 0.9 }}>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-7 w-7 shrink-0 rounded-xl hover:bg-muted"
                  onClick={() => onRemove(item.id)}
                >
                  <X className="h-3.5 w-3.5" />
                </Button>
              </motion.div>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  );
}
