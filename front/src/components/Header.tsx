import { Link, useLocation, useParams } from 'react-router-dom';
import { Library, ChevronRight, Menu, X, Map, Cpu, BarChart3, Files } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useState } from 'react';

interface HeaderProps {
  workspaceName?: string;
}

const WORKSPACE_TABS = [
  { label: 'Files',   icon: Files,    suffix: '' },
  { label: 'Map',     icon: Map,      suffix: '/map' },
  { label: 'Sensors', icon: Cpu,      suffix: '/sensors' },
  { label: 'Report',  icon: BarChart3, suffix: '/report' },
];

export function Header({ workspaceName }: HeaderProps) {
  const location = useLocation();
  const { id } = useParams();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isWorkspacePage = !!id && location.pathname.includes('/workspace/');

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        {/* Brand + breadcrumb */}
        <div className="flex items-center gap-3 min-w-0">
          <Link to="/" className="flex items-center gap-2 group shrink-0">
            <div className="p-2 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
              <Library className="h-5 w-5 text-primary" />
            </div>
            <span className="font-semibold text-lg hidden sm:block">Protocol Genesis</span>
          </Link>

          {workspaceName && (
            <>
              <ChevronRight className="h-4 w-4 text-muted-foreground hidden sm:block shrink-0" />
              <span className="text-sm text-muted-foreground hidden sm:block truncate max-w-[160px]">
                {workspaceName}
              </span>
            </>
          )}
        </div>

        {/* Workspace tab navigation (desktop) */}
        {isWorkspacePage && (
          <nav className="hidden md:flex items-center gap-1">
            {WORKSPACE_TABS.map(({ label, icon: Icon, suffix }) => {
              const to = `/workspace/${id}${suffix}`;
              const active =
                suffix === ''
                  ? location.pathname === to
                  : location.pathname.startsWith(to);
              return (
                <Link
                  key={label}
                  to={to}
                  className={cn(
                    'flex items-center gap-1.5 px-3 py-1.5 rounded-md text-sm font-medium transition-colors',
                    active
                      ? 'bg-primary/10 text-primary'
                      : 'text-muted-foreground hover:bg-muted hover:text-foreground'
                  )}
                >
                  <Icon className="h-4 w-4" />
                  {label}
                </Link>
              );
            })}
          </nav>
        )}

        {/* Global nav (desktop, non-workspace) */}
        {!isWorkspacePage && (
          <nav className="hidden md:flex items-center gap-6">
            <Link
              to="/"
              className={cn(
                'text-sm font-medium transition-colors',
                location.pathname === '/'
                  ? 'text-foreground'
                  : 'text-muted-foreground hover:text-foreground'
              )}
            >
              Workspaces
            </Link>
          </nav>
        )}

        <div className="flex items-center gap-3">
          <Button
            variant="ghost"
            size="icon"
            className="md:hidden"
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
          </Button>
        </div>
      </div>

      {/* Mobile menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-border bg-background animate-fade-in">
          <nav className="container mx-auto px-4 py-4 flex flex-col gap-2">
            {isWorkspacePage
              ? WORKSPACE_TABS.map(({ label, icon: Icon, suffix }) => {
                  const to = `/workspace/${id}${suffix}`;
                  const active =
                    suffix === ''
                      ? location.pathname === to
                      : location.pathname.startsWith(to);
                  return (
                    <Link
                      key={label}
                      to={to}
                      onClick={() => setMobileMenuOpen(false)}
                      className={cn(
                        'flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                        active
                          ? 'bg-primary/10 text-primary'
                          : 'text-muted-foreground hover:bg-muted'
                      )}
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </Link>
                  );
                })
              : [
                  { to: '/', label: 'Workspaces' },
                  { to: '/create', label: 'Create New Workspace' },
                ].map(({ to, label }) => (
                  <Link
                    key={to}
                    to={to}
                    onClick={() => setMobileMenuOpen(false)}
                    className={cn(
                      'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                      location.pathname === to
                        ? 'bg-primary/10 text-primary'
                        : 'text-muted-foreground hover:bg-muted'
                    )}
                  >
                    {label}
                  </Link>
                ))}
          </nav>
        </div>
      )}
    </header>
  );
}
