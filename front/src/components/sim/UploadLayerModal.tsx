/**
 * UploadLayerModal — modal wrapper around GeoLayerForm for MapView.
 */
import { motion, AnimatePresence } from 'framer-motion';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Dialog, DialogPortal } from '@/components/ui/dialog';
import { X, Layers } from 'lucide-react';
import { GeoLayerForm, GeoCategory } from './GeoLayerForm';

interface UploadLayerModalProps {
  open: boolean;
  onClose: () => void;
  geoCategory: GeoCategory;
  onGeoCategoryChange: (cat: GeoCategory) => void;
  onUpload: (file: File) => void;
  isUploading: boolean;
  uploadProgress: string | null;
}

export function UploadLayerModal({
  open,
  onClose,
  geoCategory,
  onGeoCategoryChange,
  onUpload,
  isUploading,
  uploadProgress,
}: UploadLayerModalProps) {
  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogPortal forceMount>
        <AnimatePresence>
          {open && (
            <>
              <DialogPrimitive.Overlay asChild forceMount>
                <motion.div
                  key="upload-layer-overlay"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.18 }}
                  className="fixed inset-0 z-[900] bg-black/60 backdrop-blur-md"
                />
              </DialogPrimitive.Overlay>

              <DialogPrimitive.Content forceMount className="fixed inset-0 z-[901] flex items-center justify-center p-4 pointer-events-none focus:outline-none">
                <motion.div
                  key="upload-layer-modal"
                  initial={{ opacity: 0, scale: 0.88, y: 20 }}
                  animate={{ opacity: 1, scale: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.9, y: 12 }}
                  transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                  className="relative w-full max-w-sm bg-card border border-border rounded-3xl overflow-hidden pointer-events-auto shadow-2xl"
                >
                  <DialogPrimitive.Title className="sr-only">Upload GIS Layer</DialogPrimitive.Title>

                  <div
                    className="flex items-center justify-between px-5 py-4 border-b border-border/50"
                    style={{ background: 'linear-gradient(135deg, hsl(0,84%,15%), hsl(220,25%,12%))' }}
                  >
                    <div className="flex items-center gap-3">
                      <div className="p-2 rounded-xl bg-white/10">
                        <Layers className="h-4 w-4 text-white" />
                      </div>
                      <span className="font-bold text-white">Upload GIS Layer</span>
                    </div>
                    <button
                      onClick={onClose}
                      className="p-1.5 rounded-xl text-white/60 hover:text-white hover:bg-white/10 transition-colors"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>

                  <div className="p-5">
                    <GeoLayerForm
                      geoCategory={geoCategory}
                      onGeoCategoryChange={onGeoCategoryChange}
                      onFileSelect={file => { onUpload(file); onClose(); }}
                      isUploading={isUploading}
                      uploadProgress={uploadProgress}
                    />
                  </div>
                </motion.div>
              </DialogPrimitive.Content>
            </>
          )}
        </AnimatePresence>
      </DialogPortal>
    </Dialog>
  );
}
