import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { RagAnswer, SearchResult } from '@/types/files';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { cn } from '@/lib/utils';
import { Search, Loader2, FileText, MessageSquare } from 'lucide-react';

interface QueryBoxProps {
  workspaceId: string;
}

type ActiveTab = 'passages' | 'answer';

export function QueryBox({ workspaceId }: QueryBoxProps) {
  const [query, setQuery] = useState('');
  const [activeTab, setActiveTab] = useState<ActiveTab>('answer');
  const [passages, setPassages] = useState<SearchResult[]>([]);
  const [ragAnswer, setRagAnswer] = useState<RagAnswer | null>(null);
  const [searched, setSearched] = useState(false);

  const searchMutation = useMutation({
    mutationFn: (q: string) =>
      api.search.query({ workspace_id: workspaceId, query: q, top_k: 5 }),
    onSuccess: (data) => setPassages(data),
  });

  const ragMutation = useMutation({
    mutationFn: (q: string) => api.rag.query({ query: q, top_k: 5 }),
    onSuccess: (data) => setRagAnswer(data),
  });

  const isPending = searchMutation.isPending || ragMutation.isPending;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!query.trim()) return;
    const q = query.trim();
    setSearched(true);
    searchMutation.mutate(q);
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
    <div className="p-4 rounded-xl bg-card border border-border space-y-4">
      <div className="flex items-center gap-2">
        <Search className="h-4 w-4 text-primary" />
        <h3 className="text-sm font-semibold">SOP Search</h3>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-2">
        <Input
          value={query}
          onChange={e => setQuery(e.target.value)}
          placeholder="e.g. What to do during a fire?"
          className="bg-muted/50 border-border text-sm"
          disabled={isPending}
        />
        <Button type="submit" size="sm" disabled={isPending || !query.trim()}>
          {isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
        </Button>
      </form>

      {searched && (
        <>
          {/* Tab bar */}
          <div className="flex gap-1 border-b border-border">
            <button
              onClick={() => setActiveTab('answer')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-t transition-colors',
                activeTab === 'answer'
                  ? 'border-b-2 border-primary text-primary -mb-px'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <MessageSquare className="h-3 w-3" />
              Answer
            </button>
            <button
              onClick={() => setActiveTab('passages')}
              className={cn(
                'flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-t transition-colors',
                activeTab === 'passages'
                  ? 'border-b-2 border-primary text-primary -mb-px'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              <FileText className="h-3 w-3" />
              Passages
            </button>
          </div>

          {/* Answer tab */}
          {activeTab === 'answer' && (
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

          {/* Passages tab */}
          {activeTab === 'passages' && (
            <div className="space-y-2">
              {searchMutation.isPending ? (
                <div className="flex items-center gap-2 text-xs text-muted-foreground py-4">
                  <Loader2 className="h-3 w-3 animate-spin" />
                  Searching passages…
                </div>
              ) : passages.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-3">
                  No relevant passages found. Try a different query or upload more documents.
                </p>
              ) : (
                passages.map(r => (
                  <div
                    key={r.chunk_id}
                    className="p-3 rounded-lg bg-muted/40 border border-border/50 space-y-1"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-1.5 min-w-0">
                        <FileText className="h-3 w-3 text-primary shrink-0" />
                        <span className="text-xs font-medium text-primary truncate">
                          {r.filename}
                        </span>
                      </div>
                      <span
                        className={cn(
                          'text-xs px-1.5 py-0.5 rounded font-mono shrink-0',
                          r.score >= 0.8
                            ? 'bg-success/20 text-success'
                            : r.score >= 0.5
                            ? 'bg-warning/20 text-warning'
                            : 'bg-muted text-muted-foreground'
                        )}
                      >
                        {(r.score * 100).toFixed(0)}%
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed line-clamp-4">
                      {r.content}
                    </p>
                  </div>
                ))
              )}
            </div>
          )}
        </>
      )}

      {!searched && (
        <p className="text-xs text-muted-foreground">
          Ask a question about your uploaded documents. The <strong>Answer</strong> tab returns a
          grounded Hebrew response; <strong>Passages</strong> shows the raw retrieved chunks.
        </p>
      )}
    </div>
  );
}
