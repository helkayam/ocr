import { useState, useEffect } from 'react';
import { X, FileText, Loader2 } from 'lucide-react';
import { CitedSource } from '@/types/files';

const BASE = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';

interface SourcePreviewPanelProps {
  source: CitedSource;
  onClose: () => void;
}

export function SourcePreviewPanel({ source, onClose }: SourcePreviewPanelProps) {
  const [imgLoaded, setImgLoaded] = useState(false);

  // Reset loading state whenever the citation changes
  useEffect(() => {
    setImgLoaded(false);
  }, [source.document_id, source.page_num]);

  const imgUrl = `${BASE}/files/${source.document_id}/page/${source.page_num}?scale=2`;

  return (
    <div className="flex flex-col h-full bg-white border-l border-border">
      {/* ── Header ── */}
      <div className="flex items-center gap-2 px-4 py-3 border-b border-border shrink-0 bg-gray-50/80">
        <FileText className="h-4 w-4 shrink-0 text-red-500" />

        <div className="flex-1 min-w-0 flex items-center gap-2" dir="rtl">
          <span
            className="text-sm font-semibold text-foreground truncate"
            title={source.file_name}
          >
            {source.file_name}
          </span>
          <span className="shrink-0 text-xs font-semibold px-1.5 py-0.5 rounded-full bg-red-50 text-red-600 border border-red-200">
            {/* ע=ע מ=מ ו=ו ד=ד */}
            {'עמוד'} {source.page_num}
          </span>
        </div>

        <button
          type="button"
          onClick={onClose}
          className="shrink-0 ml-1 p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
          title="Close preview"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* ── Scrollable PDF area ── */}
      <div className="flex-1 overflow-y-auto p-4">
        {/*
          Single-image approach with an absolute skeleton overlay:
          - The img starts at opacity 0 so the browser fetches immediately.
          - min-height on the wrapper gives the skeleton something to fill
            before the browser knows the image dimensions.
          - Once onLoad fires the skeleton unmounts and the image fades in.
        */}
        <div
          className="relative w-full"
          style={{ minHeight: imgLoaded ? undefined : '540px' }}
        >
          {/* Skeleton overlay */}
          {!imgLoaded && (
            <div className="absolute inset-0 rounded-xl bg-gradient-to-br from-gray-100 to-gray-200 animate-pulse flex items-center justify-center">
              <Loader2 className="h-8 w-8 text-muted-foreground/50 animate-spin" />
            </div>
          )}

          {/* Page image */}
          <img
            src={imgUrl}
            alt={`${source.file_name} — ${'עמוד'} ${source.page_num}`}
            className="w-full rounded-xl shadow-md block"
            style={{
              opacity: imgLoaded ? 1 : 0,
              transition: 'opacity 280ms ease',
            }}
            onLoad={() => setImgLoaded(true)}
            onError={() => setImgLoaded(true)}
          />
        </div>
      </div>
    </div>
  );
}
