import { motion, AnimatePresence } from 'framer-motion';
import { Trash2, AlertTriangle } from 'lucide-react';

interface ConfirmDeleteModalProps {
  isOpen: boolean;
  workspaceName: string;
  isDeleting?: boolean;
  onCancel: () => void;
  onConfirm: () => void;
}

export function ConfirmDeleteModal({
  isOpen,
  workspaceName,
  isDeleting = false,
  onCancel,
  onConfirm,
}: ConfirmDeleteModalProps) {
  return (
    <AnimatePresence>
      {isOpen && (
        <>
          {/* Backdrop */}
          <motion.div
            key="backdrop"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
            className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm"
            onClick={onCancel}
          />

          {/* Modal card */}
          <motion.div
            key="modal"
            initial={{ opacity: 0, scale: 0.93, y: 16 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.93, y: 16 }}
            transition={{ type: 'spring', stiffness: 380, damping: 26 }}
            className="fixed inset-0 z-50 flex items-center justify-center pointer-events-none"
          >
            <div
              className="pointer-events-auto w-full max-w-md mx-4 bg-white rounded-3xl p-8 flex flex-col gap-6"
              style={{
                boxShadow:
                  '0 20px 60px rgba(0,0,0,0.12), 0 4px 16px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.95)',
              }}
              onClick={(e) => e.stopPropagation()}
            >
              {/* Icon */}
              <div className="flex justify-center">
                <div
                  className="p-4 rounded-2xl"
                  style={{
                    background: 'linear-gradient(135deg, hsl(0,84%,96%), hsl(0,84%,92%))',
                    boxShadow: '0 4px 14px rgba(239,68,68,0.14)',
                  }}
                >
                  <AlertTriangle className="h-7 w-7 text-destructive" />
                </div>
              </div>

              {/* Text */}
              <div className="text-center space-y-2">
                <h2 className="text-xl font-bold text-foreground">Delete Workspace?</h2>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  You're about to permanently delete{' '}
                  <span className="font-semibold text-foreground">"{workspaceName}"</span> and all
                  its files. This action cannot be undone.
                </p>
              </div>

              {/* Actions */}
              <div className="flex gap-3">
                <button
                  onClick={onCancel}
                  disabled={isDeleting}
                  className="flex-1 py-2.5 rounded-2xl text-sm font-semibold text-muted-foreground bg-gray-100 hover:bg-gray-200 transition-colors disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={onConfirm}
                  disabled={isDeleting}
                  className="flex-1 flex items-center justify-center gap-2 py-2.5 rounded-2xl text-sm font-bold text-white transition-opacity disabled:opacity-70"
                  style={{
                    background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
                    boxShadow: '0 6px 20px rgba(239,68,68,0.38), inset 0 1px 0 rgba(255,255,255,0.2)',
                  }}
                >
                  <Trash2 className="h-4 w-4" />
                  {isDeleting ? 'Deleting…' : 'Delete'}
                </button>
              </div>
            </div>
          </motion.div>
        </>
      )}
    </AnimatePresence>
  );
}
