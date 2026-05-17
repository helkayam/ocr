/**
 * UploadLayerModal — Claude-style centered modal with backdrop-blur for GeoJSON layer uploads.
 */
import { useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Dialog, DialogPortal } from '@/components/ui/dialog';
import { X, Upload, Layers } from 'lucide-react';
import { cn } from '@/lib/utils';

type GeoCategory = 'cameras' | 'shelters' | 'buildings';

const GEO_CATEGORIES: { type: GeoCategory; emoji: string; label: string; desc: string }[] = [
  { type: 'shelters',  emoji: '🏠', label: 'Shelters',  desc: 'Emergency shelter points' },
  { type: 'cameras',   emoji: '📷', label: 'Cameras',   desc: 'Surveillance camera points' },
  { type: 'buildings', emoji: '🏢', label: 'Buildings', desc: 'Building polygon layer' },
];

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
  const fileInputRef = useRef<HTMLInputElement>(null);

  return (
    <Dialog open={open} onOpenChange={v => !v && onClose()}>
      <DialogPortal forceMount>
        <AnimatePresence>
          {open && (
            <>
              {/* Backdrop */}
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

              {/* Modal */}
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

                  {/* Header */}
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

                  <div className="p-5 space-y-4">
                    {/* Category */}
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

                    {/* File upload area */}
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".geojson,.json"
                      className="hidden"
                      onChange={e => {
                        const file = e.target.files?.[0];
                        if (file) { onUpload(file); onClose(); }
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
                </motion.div>
              </DialogPrimitive.Content>
            </>
          )}
        </AnimatePresence>
      </DialogPortal>
    </Dialog>
  );
}
