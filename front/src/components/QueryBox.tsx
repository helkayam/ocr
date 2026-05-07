import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { RagAnswer } from '@/types/files';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Search, Loader2, MapPin, X } from 'lucide-react';

interface QueryBoxProps {
  workspaceId: string;
  activeMapContext?: string | null;
  onClearContext?: () => void;
}

export function QueryBox({ workspaceId, activeMapContext, onClearContext }: QueryBoxProps) {
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

  // Split Hebrew answer into main body and citation footer
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
    <div dir="rtl" className="p-4 rounded-xl bg-card border border-border space-y-4">
      <div className="flex items-center gap-2">
        <Search className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">SOP Search</h3>
      </div>

      {activeMapContext && (
        <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-primary/10 border border-primary/30 text-xs">
          <MapPin className="h-3 w-3 text-primary shrink-0" />
          <span className="text-primary font-medium flex-1 truncate">
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
        </div>
      )}

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          dir="rtl"
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="לדוגמה: מה לעשות במקרה של שריפה?"
          className="bg-muted/50 border-border text-sm"
          disabled={ragMutation.isPending}
        />
        <Button type="submit" size="sm" disabled={ragMutation.isPending || !query.trim()}>
          {ragMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        </Button>
      </form>

      {searched && (
        <div className="min-h-[80px]">
          {ragMutation.isPending ? (
            <div className="flex items-center gap-2 text-xs text-muted-foreground py-4">
              <Loader2 className="h-3 w-3 animate-spin" />
              Generating Hebrew answer…
            </div>
          ) : ragAnswer ? (
            (() => {
              const { body, footer } = parseAnswer(ragAnswer.answer);
              return (
                <div className="space-y-3">
                  <div
                    dir="rtl"
                    lang="he"
                    className="text-sm text-foreground leading-relaxed whitespace-pre-wrap"
                  >
                    {body}
                  </div>
                  {footer && (
                    <div
                      dir="rtl"
                      lang="he"
                      className="text-xs text-muted-foreground border-t border-border/50 pt-2"
                    >
                      {footer}
                    </div>
                  )}
                </div>
              );
            })()
          ) : (
            <p className="text-xs text-muted-foreground text-center py-3">
              No answer returned. Try uploading indexed PDF documents first.
            </p>
          )}
        </div>
      )}

      {!searched && (
        <p className="text-xs text-muted-foreground">
          שאל שאלה על המסמכים שהועלו כדי לקבל תשובה מבוססת מקורות בעברית.
        </p>
      )}
    </div>
  );
}
