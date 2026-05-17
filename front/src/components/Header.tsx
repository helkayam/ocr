import { Link, useLocation, useParams } from 'react-router-dom';
import { Library, ChevronRight, Menu, X, Map, BarChart3, Files, Upload } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface HeaderProps {
  workspaceName?: string;
  onUploadClick?: () => void;
}

const WORKSPACE_TABS = [
  { label: 'Files',  icon: Files,     suffix: '' },
  { label: 'Map',    icon: Map,       suffix: '/map' },
  { label: 'Report', icon: BarChart3, suffix: '/report' },
];

export function Header({ workspaceName, onUploadClick }: HeaderProps) {
  const location = useLocation();
  const { id } = useParams();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isWorkspacePage = !!id && location.pathname.includes('/workspace/');

  return (
    <header className="sticky top-0 z-50 w-full">
      <div className="glass border-b border-white/50 backdrop-blur-2xl">
        <div className="container mx-auto px-4 h-16 flex items-center justify-between">
          {/* Brand + breadcrumb */}
          <div className="flex items-center gap-3 min-w-0">
            <Link to="/" className="flex items-center gap-2.5 group shrink-0">
              <motion.div
                whileHover={{ scale: 1.08, rotate: -5 }}
                whileTap={{ scale: 0.93 }}
                transition={{ type: 'spring', stiffness: 400, damping: 17 }}
                className="p-2 rounded-2xl flex items-center justify-center"
                style={{
                  background: 'linear-gradient(135deg, hsl(0,84%,58%) 0%, hsl(0,84%,44%) 100%)',
                  boxShadow: '0 4px 12px rgba(239,68,68,0.38), inset 0 1px 0 rgba(255,255,255,0.25)',
                }}
              >
                <Library className="h-5 w-5 text-white" />
              </motion.div>
              <span className="font-bold text-lg hidden sm:block text-gradient">Protocol Genesis</span>
            </Link>

            {workspaceName && (
              <>
                <ChevronRight className="h-4 w-4 text-muted-foreground hidden sm:block shrink-0" />
                <span className="text-sm text-muted-foreground hidden sm:block truncate max-w-[160px] font-medium">
                  {workspaceName}
                </span>
              </>
            )}
          </div>

          {/* Workspace tab navigation (desktop) */}
          {isWorkspacePage && (
            <nav className="hidden md:flex items-center gap-1 p-1 rounded-2xl bg-muted/60 border border-white/60"
              style={{ boxShadow: 'inset 0 1px 3px rgba(0,0,0,0.05)' }}>
              {WORKSPACE_TABS.map(({ label, icon: Icon, suffix }) => {
                const to = `/workspace/${id}${suffix}`;
                const active =
                  suffix === ''
                    ? location.pathname === to
                    : location.pathname.startsWith(to);
                return (
                  <Link key={label} to={to}>
                    <motion.div
                      whileHover={{ scale: 1.04 }}
                      whileTap={{ scale: 0.95 }}
                      transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                      className={cn(
                        'flex items-center gap-1.5 px-3 py-1.5 rounded-xl text-sm font-medium transition-all duration-200 cursor-pointer',
                        active
                          ? 'text-white'
                          : 'text-muted-foreground hover:text-foreground hover:bg-white/60'
                      )}
                      style={active ? {
                        background: 'linear-gradient(135deg, hsl(0,84%,55%), hsl(0,84%,42%))',
                        boxShadow: '0 2px 8px rgba(239,68,68,0.38), inset 0 1px 0 rgba(255,255,255,0.2)',
                      } : {}}
                    >
                      <Icon className="h-4 w-4" />
                      {label}
                    </motion.div>
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
                  'text-sm font-semibold transition-colors',
                  location.pathname === '/'
                    ? 'text-gradient'
                    : 'text-muted-foreground hover:text-foreground'
                )}
              >
                Workspaces
              </Link>
            </nav>
          )}

          <div className="flex items-center gap-3">
            {onUploadClick && (
              <motion.button
                whileHover={{ scale: 1.04 }}
                whileTap={{ scale: 0.92 }}
                transition={{ type: 'spring', stiffness: 400, damping: 17 }}
                onClick={onUploadClick}
                className="hidden sm:flex items-center gap-2 px-4 py-2 rounded-2xl text-sm font-bold text-white"
                style={{
                  background: 'linear-gradient(135deg, hsl(0,84%,55%) 0%, hsl(0,84%,42%) 100%)',
                  boxShadow: '0 4px 14px rgba(239,68,68,0.42), inset 0 1px 0 rgba(255,255,255,0.2)',
                }}
              >
                <Upload className="h-4 w-4" />
                + Upload Files
              </motion.button>
            )}

            <motion.div whileTap={{ scale: 0.9 }} className="md:hidden">
              <Button
                variant="ghost"
                size="icon"
                className="rounded-xl"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                {mobileMenuOpen ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
              </Button>
            </motion.div>
          </div>
        </div>
      </div>

      {/* Mobile menu */}
      <AnimatePresence>
        {mobileMenuOpen && (
          <motion.div
            initial={{ opacity: 0, y: -10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ type: 'spring', stiffness: 400, damping: 30 }}
            className="md:hidden glass border-b border-white/50"
          >
            <nav className="container mx-auto px-4 py-4 flex flex-col gap-2">
              {onUploadClick && (
                <motion.button
                  whileTap={{ scale: 0.96 }}
                  onClick={() => { onUploadClick(); setMobileMenuOpen(false); }}
                  className="flex items-center gap-2 px-4 py-2.5 rounded-2xl text-sm font-bold text-white"
                  style={{
                    background: 'linear-gradient(135deg, hsl(0,84%,55%), hsl(0,84%,42%))',
                    boxShadow: '0 2px 8px rgba(239,68,68,0.35)',
                  }}
                >
                  <Upload className="h-4 w-4" />
                  + Upload Files
                </motion.button>
              )}

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
                          'flex items-center gap-2 px-4 py-2.5 rounded-2xl text-sm font-medium transition-all duration-200',
                          active
                            ? 'text-white'
                            : 'text-muted-foreground hover:bg-white/60'
                        )}
                        style={active ? {
                          background: 'linear-gradient(135deg, hsl(0,84%,55%), hsl(0,84%,42%))',
                          boxShadow: '0 2px 8px rgba(239,68,68,0.3)',
                        } : {}}
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
                        'px-4 py-2.5 rounded-2xl text-sm font-medium transition-all duration-200',
                        location.pathname === to
                          ? 'text-white'
                          : 'text-muted-foreground hover:bg-white/60'
                      )}
                      style={location.pathname === to ? {
                        background: 'linear-gradient(135deg, hsl(0,84%,55%), hsl(0,84%,42%))',
                        boxShadow: '0 2px 8px rgba(239,68,68,0.3)',
                      } : {}}
                    >
                      {label}
                    </Link>
                  ))}
            </nav>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
