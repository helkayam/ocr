import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Header } from '@/components/Header';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { ArrowLeft, CheckCircle2, XCircle, AlertTriangle, RefreshCw, ShieldCheck } from 'lucide-react';

export default function ReportView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: workspace } = useQuery({
    queryKey: ['workspace', id],
    queryFn: () => api.workspaces.get(id!),
    enabled: !!id,
  });

  const {
    data: report,
    isLoading,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ['report', id],
    queryFn: () => api.report.get(id!),
    enabled: !!id,
    staleTime: 0,
  });

  const scoreColor =
    !report ? 'text-muted-foreground' :
    report.score >= 80 ? 'text-success' :
    report.score >= 50 ? 'text-warning' :
    'text-destructive';

  const scoreRing =
    !report ? 'stroke-muted' :
    report.score >= 80 ? 'stroke-success' :
    report.score >= 50 ? 'stroke-warning' :
    'stroke-destructive';

  const circumference = 2 * Math.PI * 45;
  const offset = report ? circumference - (report.score / 100) * circumference : circumference;

  return (
    <div className="min-h-screen bg-background">
      <Header workspaceName={workspace?.name} />

      <main className="container mx-auto px-4 py-8 max-w-4xl">
        <div className="flex items-center justify-between mb-8">
          <Button variant="ghost" size="sm" onClick={() => navigate(`/workspace/${id}`)}>
            <ArrowLeft className="h-4 w-4 mr-2" />
            Back to Files
          </Button>
          <Button variant="outline" size="sm" onClick={() => refetch()} disabled={isFetching}>
            <RefreshCw className={cn('h-4 w-4 mr-2', isFetching && 'animate-spin')} />
            Refresh
          </Button>
        </div>

        <div className="flex items-center gap-3 mb-8">
          <ShieldCheck className="h-8 w-8 text-primary" />
          <div>
            <h1 className="text-2xl font-bold">Readiness Report</h1>
            <p className="text-muted-foreground text-sm">
              Gap analysis between your SOPs, sensors, and map data.
            </p>
          </div>
        </div>

        {isLoading ? (
          <div className="flex items-center justify-center py-20">
            <RefreshCw className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : report ? (
          <div className="space-y-6 animate-fade-in">
            {/* Score card */}
            <div className="p-6 rounded-xl bg-card border border-border flex flex-col sm:flex-row items-center gap-8">
              <div className="relative w-32 h-32 shrink-0">
                <svg viewBox="0 0 100 100" className="w-32 h-32 -rotate-90">
                  <circle cx="50" cy="50" r="45" fill="none" stroke="hsl(var(--muted))" strokeWidth="8" />
                  <circle
                    cx="50" cy="50" r="45" fill="none"
                    className={cn('transition-all duration-700', scoreRing)}
                    strokeWidth="8"
                    strokeLinecap="round"
                    strokeDasharray={circumference}
                    strokeDashoffset={offset}
                  />
                </svg>
                <div className="absolute inset-0 flex flex-col items-center justify-center">
                  <span className={cn('text-3xl font-bold', scoreColor)}>{report.score}%</span>
                  <span className="text-xs text-muted-foreground">ready</span>
                </div>
              </div>

              <div className="flex-1 space-y-2">
                <p className="font-semibold text-lg">
                  {report.score >= 80
                    ? 'System is well prepared'
                    : report.score >= 50
                    ? 'System partially ready — action needed'
                    : 'System has critical gaps'}
                </p>
                <div className="flex flex-wrap gap-4 text-sm">
                  <span className="text-muted-foreground">
                    <span className="text-foreground font-medium">{report.total_files}</span> files
                  </span>
                  <span className="text-muted-foreground">
                    <span className="text-foreground font-medium">{report.total_sensors}</span> sensors
                  </span>
                  {report.file_types.length > 0 && (
                    <span className="text-muted-foreground">
                      Types: <span className="text-foreground">{report.file_types.join(', ')}</span>
                    </span>
                  )}
                </div>
              </div>
            </div>

            {/* Covered */}
            {report.covered.length > 0 && (
              <Section title="Covered" icon={CheckCircle2} iconClass="text-success" count={report.covered.length}>
                {report.covered.map((item, i) => (
                  <Item key={i} icon={CheckCircle2} iconClass="text-success" text={item} />
                ))}
              </Section>
            )}

            {/* Gaps */}
            {report.gaps.length > 0 && (
              <Section title="Critical Gaps" icon={XCircle} iconClass="text-destructive" count={report.gaps.length}>
                {report.gaps.map((item, i) => (
                  <Item key={i} icon={XCircle} iconClass="text-destructive" text={item} />
                ))}
              </Section>
            )}

            {/* Warnings */}
            {report.warnings.length > 0 && (
              <Section title="Warnings" icon={AlertTriangle} iconClass="text-warning" count={report.warnings.length}>
                {report.warnings.map((item, i) => (
                  <Item key={i} icon={AlertTriangle} iconClass="text-warning" text={item} />
                ))}
              </Section>
            )}
          </div>
        ) : (
          <p className="text-muted-foreground text-center py-20">Failed to load report.</p>
        )}
      </main>
    </div>
  );
}

function Section({
  title, icon: Icon, iconClass, count, children
}: {
  title: string;
  icon: React.FC<any>;
  iconClass: string;
  count: number;
  children: React.ReactNode;
}) {
  return (
    <div className="p-5 rounded-xl bg-card border border-border space-y-3">
      <div className="flex items-center gap-2">
        <Icon className={cn('h-5 w-5', iconClass)} />
        <h2 className="font-semibold">{title}</h2>
        <span className="ml-auto text-sm text-muted-foreground">{count}</span>
      </div>
      <ul className="space-y-2">{children}</ul>
    </div>
  );
}

function Item({
  icon: Icon, iconClass, text
}: {
  icon: React.FC<any>;
  iconClass: string;
  text: string;
}) {
  return (
    <li className="flex items-start gap-2.5">
      <Icon className={cn('h-4 w-4 shrink-0 mt-0.5', iconClass)} />
      <span className="text-sm text-muted-foreground">{text}</span>
    </li>
  );
}
