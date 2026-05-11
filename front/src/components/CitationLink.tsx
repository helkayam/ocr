import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/components/ui/tooltip';
import { CitedSource } from '@/types/files';

interface CitationLinkProps {
  pageNum: number;
  source: CitedSource | null;
  onClick?: () => void;
}

export function CitationLink({ pageNum, source, onClick }: CitationLinkProps) {
  const label = `עמוד ${pageNum}`; // עמוד N

  if (!source || !onClick) {
    return (
      <span className="text-muted-foreground text-xs">
        {label}
      </span>
    );
  }

  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <button
            type="button"
            onClick={onClick}
            className="inline-flex items-center px-1.5 py-0.5 rounded text-xs font-semibold mx-0.5 transition-all hover:scale-105 active:scale-95"
            style={{
              color: 'hsl(0,84%,45%)',
              background: 'hsla(0,84%,55%,0.09)',
              border: '1px solid hsla(0,84%,55%,0.28)',
            }}
          >
            {label}
          </button>
        </TooltipTrigger>
        {source.text_snippet && (
          <TooltipContent
            side="top"
            className="max-w-xs text-xs leading-relaxed"
            dir="rtl"
          >
            {source.text_snippet.slice(0, 140)}
            {source.text_snippet.length > 140 ? '…' : ''}
          </TooltipContent>
        )}
      </Tooltip>
    </TooltipProvider>
  );
}
