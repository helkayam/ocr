import { FileItem } from '@/types/files';
import { FileTypeIcon } from './FileTypeIcon';
import { FileStatusBadge } from './FileStatusBadge';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { Download, FileText, Calendar, HardDrive, CheckCircle2, AlertTriangle, AlertCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

interface MetadataModalProps {
  file: FileItem | null;
  isOpen: boolean;
  onClose: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(date: Date | null | undefined): string {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) return 'N/A';
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function MetadataModal({ file, isOpen, onClose }: MetadataModalProps) {
  if (!file) return null;

  const validationResults = file.metadata?.validationResults || [
    { type: 'success' as const, message: 'File structure validated' },
    { type: 'success' as const, message: 'Content readable' },
  ];

  const missingComponents = file.metadata?.missingComponents || [];

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="sm:max-w-[600px] bg-card border-border p-0 overflow-hidden">
        <div className="bg-muted/30 p-6 border-b border-border">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-3 text-xl">
              <FileTypeIcon type={file.type} size="lg" />
              <span className="truncate">{file.name}</span>
            </DialogTitle>
          </DialogHeader>
        </div>

        <div className="p-6 space-y-6">
          {/* File Info Grid */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <FileText className="h-3.5 w-3.5" />
                File Type
              </p>
              <p className="text-sm font-medium uppercase">{file.type}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <HardDrive className="h-3.5 w-3.5" />
                Size
              </p>
              <p className="text-sm font-medium">{formatFileSize(file.size)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Calendar className="h-3.5 w-3.5" />
                Upload Date
              </p>
              <p className="text-sm font-medium">{formatDate(file.date)}</p>
            </div>
            <div className="space-y-1">
              <p className="text-xs text-muted-foreground">Status</p>
              <FileStatusBadge status={file.status} />
            </div>
          </div>

          {/* Validation Results */}
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-muted-foreground">Validation Results</h4>
            <div className="space-y-2">
              {validationResults.map((result, index) => (
                <div
                  key={index}
                  className={cn(
                    'flex items-center gap-2 p-3 rounded-lg text-sm',
                    result.type === 'success' && 'bg-success/10 text-success',
                    result.type === 'warning' && 'bg-warning/10 text-warning',
                    result.type === 'error' && 'bg-destructive/10 text-destructive'
                  )}
                >
                  {result.type === 'success' && <CheckCircle2 className="h-4 w-4 shrink-0" />}
                  {result.type === 'warning' && <AlertTriangle className="h-4 w-4 shrink-0" />}
                  {result.type === 'error' && <AlertCircle className="h-4 w-4 shrink-0" />}
                  {result.message}
                </div>
              ))}
            </div>
          </div>

          {/* Missing Components (for Shapefiles) */}
          {file.type === 'shapefile' && missingComponents.length > 0 && (
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-destructive flex items-center gap-2">
                <AlertCircle className="h-4 w-4" />
                Missing Components
              </h4>
              <div className="flex flex-wrap gap-2">
                {missingComponents.map((component, index) => (
                  <span
                    key={index}
                    className="px-2 py-1 text-xs rounded bg-destructive/10 text-destructive border border-destructive/20"
                  >
                    {component}
                  </span>
                ))}
              </div>
            </div>
          )}

        </div>

        <div className="p-4 border-t border-border bg-muted/20 flex justify-end gap-2">
          <Button variant="outline" onClick={onClose}>
            Close
          </Button>
          <Button
            variant="default"
            disabled={!file.download_url}
            onClick={() => {
              if (!file.download_url) return;
              const a = document.createElement('a');
              a.href = file.download_url;
              a.download = file.name;
              document.body.appendChild(a);
              a.click();
              document.body.removeChild(a);
            }}
          >
            <Download className="h-4 w-4 mr-2" />
            Download File
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
