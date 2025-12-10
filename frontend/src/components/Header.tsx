import { Link, useLocation } from 'react-router-dom';
import { Library, ChevronRight, Menu, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import { useState } from 'react';

interface HeaderProps {
  workspaceName?: string;
}

export function Header({ workspaceName }: HeaderProps) {
  const location = useLocation();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const isWorkspacePage = location.pathname.includes('/workspace/');

  return (
    <header className="sticky top-0 z-50 w-full border-b border-border bg-background/80 backdrop-blur-xl">
      <div className="container mx-auto px-4 h-16 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Link 
            to="/" 
            className="flex items-center gap-2 group"
          >
            <div className="p-2 rounded-lg bg-primary/10 group-hover:bg-primary/20 transition-colors">
              <Library className="h-5 w-5 text-primary" />
            </div>
            <span className="font-semibold text-lg hidden sm:block">
              Digital Librarian
            </span>
          </Link>

          {workspaceName && (
            <>
              <ChevronRight className="h-4 w-4 text-muted-foreground hidden sm:block" />
              <span className="text-sm text-muted-foreground hidden sm:block truncate max-w-[200px]">
                {workspaceName}
              </span>
            </>
          )}
        </div>

        {/* Desktop Navigation */}
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
          <Link 
            to="/create"
            className={cn(
              'text-sm font-medium transition-colors',
              location.pathname === '/create' 
                ? 'text-foreground' 
                : 'text-muted-foreground hover:text-foreground'
            )}
          >
            Create New
          </Link>
        </nav>

        <div className="flex items-center gap-3">
          <Button variant="default" size="sm" className="hidden sm:flex" asChild>
            <Link to="/create">
              New Workspace
            </Link>
          </Button>

          {/* Mobile Menu Button */}
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

      {/* Mobile Menu */}
      {mobileMenuOpen && (
        <div className="md:hidden border-t border-border bg-background animate-fade-in">
          <nav className="container mx-auto px-4 py-4 flex flex-col gap-2">
            <Link 
              to="/"
              onClick={() => setMobileMenuOpen(false)}
              className={cn(
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                location.pathname === '/' 
                  ? 'bg-primary/10 text-primary' 
                  : 'text-muted-foreground hover:bg-muted'
              )}
            >
              Workspaces
            </Link>
            <Link 
              to="/create"
              onClick={() => setMobileMenuOpen(false)}
              className={cn(
                'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                location.pathname === '/create' 
                  ? 'bg-primary/10 text-primary' 
                  : 'text-muted-foreground hover:bg-muted'
              )}
            >
              Create New Workspace
            </Link>
          </nav>
        </div>
      )}
    </header>
  );
}
