import { Workspace } from '@/types/files';
import { Folder, Calendar, FileStack, ChevronRight, HardDrive } from 'lucide-react';
import { cn } from '@/lib/utils';

interface WorkspaceCardProps {
  workspace: Workspace;
  onClick: () => void;
}

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  return `${(bytes / (1024 * 1024 * 1024)).toFixed(1)} GB`;
}

function formatDate(date: Date): string {
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

export function WorkspaceCard({ workspace, onClick }: WorkspaceCardProps) {
  return (
    <button
      onClick={onClick}
      className={cn(
        'w-full text-left p-6 rounded-xl transition-all duration-300',
        'bg-card border border-border hover:border-primary/50',
        'group relative overflow-hidden',
        'hover:shadow-lg hover:shadow-primary/5',
        'focus:outline-none focus:ring-2 focus:ring-primary/50'
      )}
    >
      {/* Subtle gradient overlay on hover */}
      <div className="absolute inset-0 bg-gradient-to-br from-primary/5 to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300" />
      
      <div className="relative z-10">
        <div className="flex items-start justify-between mb-4">
          <div className="p-3 rounded-lg bg-primary/10 text-primary group-hover:bg-primary/20 transition-colors">
            <Folder className="h-6 w-6" />
          </div>
          <ChevronRight className="h-5 w-5 text-muted-foreground opacity-0 group-hover:opacity-100 group-hover:translate-x-1 transition-all" />
        </div>

        <h3 className="text-lg font-semibold text-foreground mb-2 group-hover:text-primary transition-colors">
          {workspace.name}
        </h3>
        
        {workspace.description && (
          <p className="text-sm text-muted-foreground mb-4 line-clamp-2">
            {workspace.description}
          </p>
        )}

        <div className="flex flex-wrap gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1.5">
            <Calendar className="h-3.5 w-3.5" />
            {formatDate(workspace.createdAt)}
          </span>
          <span className="flex items-center gap-1.5">
            <FileStack className="h-3.5 w-3.5" />
            {workspace.fileCount} file{workspace.fileCount !== 1 ? 's' : ''}
          </span>
          <span className="flex items-center gap-1.5">
            <HardDrive className="h-3.5 w-3.5" />
            {formatFileSize(workspace.totalSize)}
          </span>
        </div>
      </div>

      {/* Border glow effect */}
      <div className="absolute inset-0 rounded-xl border border-primary/0 group-hover:border-primary/30 transition-colors duration-300" />
    </button>
  );
}
