import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { CitedSource, RagAnswer } from '@/types/files';
import { Input } from '@/components/ui/input';
import { Search, Loader2, MapPin, X, Sparkles } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { AnswerBody } from '@/components/AnswerBody';

interface QueryBoxProps {
  workspaceId: string;
  activeMapContext?: string | null;
  onClearContext?: () => void;
  onCitationClick?: (source: CitedSource) => void;
}

export function QueryBox({ workspaceId, activeMapContext, onClearContext, onCitationClick }: QueryBoxProps) {
  const [query, setQuery] = useState('');
  const [ragAnswer, setRagAnswer] = useState<RagAnswer | null>(null);
  const [searched, setSearched] = useState(false);

  const ragMutation = useMutation({
    mutationFn: (q: string) => api.rag.query({ query: q, top_k: 5, workspace_id: workspaceId }),
    onSuccess: (data) => setRagAnswer(data),
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    const raw = query.trim();
    const q = activeMapContext ? `[Context: ${activeMapContext}] ${raw}` : raw;
    setSearched(true);
    ragMutation.mutate(q);
  };

  const parseAnswer = (answer: string) => {
    const footerMarker = 'מספרי העמודים עליהם הסתמכתי';
    const idx = answer.lastIndexOf(footerMarker);
    if (idx === -1) return { body: answer.trim(), footer: null };
    return {
      body: answer.slice(0, idx).trim(),
      footer: answer.slice(idx).trim(),
    };
  };

  return (
    <div
      dir="rtl"
      className="rounded-3xl bg-white border border-white/80 p-5 space-y-4"
      style={{
        boxShadow: '0 8px 32px rgba(239,68,68,0.08), 0 2px 8px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.95)',
      }}
    >
      {/* Header */}
      <div className="flex items-center gap-2.5">
        <div
          className="p-2 rounded-xl"
          style={{
            background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
            boxShadow: '0 3px 10px rgba(239,68,68,0.32), inset 0 1px 0 rgba(255,255,255,0.2)',
          }}
        >
          <Sparkles className="h-4 w-4 text-white" />
        </div>
        <h3 className="text-sm font-bold text-gradient">SOP Search</h3>
      </div>

      {/* Map context pill */}
      <AnimatePresence>
        {activeMapContext && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="flex items-center gap-2 px-3 py-2 rounded-2xl border text-xs"
            style={{
              background: 'hsla(0,0%,97%,1)',
              borderColor: 'hsla(0,84%,60%,0.25)',
            }}
          >
            <MapPin className="h-3 w-3 shrink-0" style={{ color: 'hsl(0,84%,55%)' }} />
            <span className="font-semibold flex-1 truncate" style={{ color: 'hsl(0,84%,50%)' }}>
              Context Active: {activeMapContext}
            </span>
            <button
              type="button"
              onClick={onClearContext}
              className="text-muted-foreground hover:text-foreground transition-colors shrink-0"
              title="Clear context"
            >
              <X className="h-3 w-3" />
            </button>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Search form */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <div className="relative flex-1">
          <Input
            dir="rtl"
            value={query}
            onChange={e => setQuery(e.target.value)}
            placeholder="לדוגמה: מה לעשות במקרה של שריפה?"
            className="text-sm pr-4 pl-4 py-2.5 rounded-2xl border-0 bg-muted/60 focus-visible:ring-2 focus-visible:ring-primary/30"
            style={{ boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.06)' }}
            disabled={ragMutation.isPending}
          />
        </div>
        <motion.button
          type="submit"
          disabled={ragMutation.isPending || !query.trim()}
          whileHover={{ scale: 1.06 }}
          whileTap={{ scale: 0.93 }}
          transition={{ type: 'spring', stiffness: 400, damping: 18 }}
          className="px-4 py-2 rounded-2xl text-white font-semibold disabled:opacity-50 disabled:pointer-events-none flex items-center justify-center min-w-[44px]"
          style={{
            background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
            boxShadow: '0 4px 14px rgba(239,68,68,0.38), inset 0 1px 0 rgba(255,255,255,0.2)',
          }}
        >
          {ragMutation.isPending
            ? <Loader2 className="h-4 w-4 animate-spin" />
            : <Search className="h-4 w-4" />
          }
        </motion.button>
      </form>

      {/* Answer area */}
      <AnimatePresence mode="wait">
        {searched && (
          <motion.div
            key="answer"
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="min-h-[80px]"
          >
            {ragMutation.isPending ? (
              <div className="flex items-center gap-2.5 text-xs text-muted-foreground py-5 justify-center">
                <div
                  className="p-1.5 rounded-lg"
                  style={{ background: 'linear-gradient(135deg, hsl(0,84%,55%), hsl(0,84%,42%))' }}
                >
                  <Loader2 className="h-3 w-3 text-white animate-spin" />
                </div>
                Generating Hebrew answer…
              </div>
            ) : ragAnswer ? (
              (() => {
                const { body, footer } = parseAnswer(ragAnswer.answer);
                return (
                  <div
                    className="space-y-3 p-4 rounded-2xl"
                    style={{
                      background: 'linear-gradient(135deg, hsla(0,0%,99%,0.95), hsla(0,0%,97%,0.95))',
                      boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.05)',
                    }}
                  >
                    <AnswerBody
                      body={body}
                      sources={ragAnswer.sources ?? []}
                      onCitationClick={onCitationClick ?? (() => {})}
                    />
                    {footer && (
                      <div
                        dir="rtl"
                        lang="he"
                        className="text-xs text-muted-foreground pt-3 border-t"
                        style={{ borderColor: 'hsl(0,0%,90%)' }}
                      >
                        {footer}
                      </div>
                    )}
                  </div>
                );
              })()
            ) : (
              <p className="text-xs text-muted-foreground text-center py-4">
                No answer returned. Try uploading indexed PDF documents first.
              </p>
            )}
          </motion.div>
        )}
      </AnimatePresence>

      {!searched && (
        <p className="text-xs text-muted-foreground leading-relaxed">
          שאל שאלה על המסמכים שהועלו כדי לקבל תשובה מבוססת מקורות בעברית.
        </p>
      )}
    </div>
  );
}
