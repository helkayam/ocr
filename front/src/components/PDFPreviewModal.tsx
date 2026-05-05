import { FileItem } from '@/types/files';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';

interface PDFPreviewModalProps {
  file: FileItem | null;
  isOpen: boolean;
  onClose: () => void;
}

export function PDFPreviewModal({ file, isOpen, onClose }: PDFPreviewModalProps) {
  if (!file) return null;

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-4xl w-full h-[85vh] flex flex-col p-0 gap-0">
        <DialogHeader className="px-6 py-4 border-b border-border shrink-0">
          <DialogTitle className="truncate">{file.name}</DialogTitle>
        </DialogHeader>
        <div className="flex-1 overflow-hidden">
          {file.preview_url ? (
            <iframe
              src={file.preview_url}
              className="w-full h-full border-0"
              title={file.name}
            />
          ) : (
            <p className="text-muted-foreground text-center py-16">
              Preview not available for this file.
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
