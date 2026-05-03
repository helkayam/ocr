import { X, CheckCircle2, AlertCircle, Loader2 } from 'lucide-react';
import { UploadQueueItem, FileType } from '@/types/files';
import { FileTypeIcon } from './FileTypeIcon';
import { Progress } from '@/components/ui/progress';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';

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
    case 'shp':
    case 'dbf':
    case 'shx':
    case 'prj': return 'shapefile';
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
    <div className="space-y-3 animate-fade-in">
      <h4 className="text-sm font-medium text-muted-foreground flex items-center gap-2">
        <Loader2 className="h-4 w-4 animate-spin" />
        Upload Queue ({items.length} file{items.length > 1 ? 's' : ''})
      </h4>
      
      <div className="space-y-2 max-h-64 overflow-y-auto scrollbar-thin pr-2">
        {items.map((item) => (
          <div
            key={item.id}
            className={cn(
              'flex items-center gap-3 p-3 rounded-lg transition-all duration-300',
              'bg-card border border-border',
              item.status === 'error' && 'border-destructive/50 bg-destructive/5',
              item.status === 'completed' && 'border-foreground/20 bg-foreground/5'
            )}
          >
            <FileTypeIcon type={getFileType(item.file.name)} size="md" />
            
            <div className="flex-1 min-w-0">
              <div className="flex items-center justify-between mb-1">
                <p className="text-sm font-medium truncate pr-4">
                  {item.file.name}
                </p>
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {formatFileSize(item.file.size)}
                </span>
              </div>
              
              {item.status === 'uploading' && (
                <div className="space-y-1">
                  <Progress value={item.progress} className="h-1.5" />
                  <p className="text-xs text-primary">{item.progress}%</p>
                </div>
              )}
              
              {item.status === 'error' && (
                <p className="text-xs text-destructive flex items-center gap-1">
                  <AlertCircle className="h-3 w-3" />
                  {item.error || 'Upload failed'}
                </p>
              )}
              
              {item.status === 'completed' && (
                <p className="text-xs text-foreground flex items-center gap-1">
                  <CheckCircle2 className="h-3 w-3" />
                  Uploaded successfully
                </p>
              )}
            </div>

            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 shrink-0"
              onClick={() => onRemove(item.id)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        ))}
      </div>
    </div>
  );
}
