import { Workspace } from '@/types/files';
import { Folder, Calendar, FileStack, HardDrive, ArrowRight } from 'lucide-react';
import { motion } from 'framer-motion';

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

function formatDate(date: Date | null | undefined): string {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) return 'N/A';
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  }).format(date);
}

const CARD_PALETTES = [
  { from: 'hsl(0,84%,58%)',  to: 'hsl(0,84%,44%)',  glow: 'rgba(239,68,68,0.22)'  },
  { from: 'hsl(0,0%,18%)',   to: 'hsl(0,0%,9%)',    glow: 'rgba(0,0,0,0.15)'      },
  { from: 'hsl(0,84%,52%)',  to: 'hsl(0,0%,14%)',   glow: 'rgba(239,68,68,0.18)'  },
  { from: 'hsl(0,0%,14%)',   to: 'hsl(0,84%,46%)',  glow: 'rgba(239,68,68,0.16)'  },
];

export function WorkspaceCard({ workspace, onClick }: WorkspaceCardProps) {
  const palette = CARD_PALETTES[(workspace.name.charCodeAt(0) || 0) % CARD_PALETTES.length];

  return (
    <motion.button
      onClick={onClick}
      className="w-full h-full text-left focus:outline-none focus:ring-2 focus:ring-primary/40 focus:ring-offset-2 rounded-3xl"
      whileHover={{ scale: 1.03, y: -4 }}
      whileTap={{ scale: 0.97 }}
      transition={{ type: 'spring', stiffness: 380, damping: 22 }}
    >
      <div
        className="relative overflow-hidden rounded-3xl bg-white border border-white/80 p-6 group h-full flex flex-col"
        style={{
          boxShadow: `0 8px 32px ${palette.glow}, 0 2px 8px rgba(0,0,0,0.06), inset 0 1px 0 rgba(255,255,255,0.95)`,
        }}
      >
        {/* Subtle gradient tint top-right */}
        <div
          className="absolute -top-8 -right-8 w-32 h-32 rounded-full opacity-15 blur-2xl transition-opacity duration-300 group-hover:opacity-25"
          style={{ background: `radial-gradient(circle, ${palette.from}, ${palette.to})` }}
        />

        <div className="relative z-10 flex flex-col flex-1">
          {/* Icon + arrow row */}
          <div className="flex items-start justify-between mb-4">
            <div
              className="p-3 rounded-2xl"
              style={{
                background: `linear-gradient(135deg, ${palette.from} 0%, ${palette.to} 100%)`,
                boxShadow: `0 4px 14px ${palette.glow}, inset 0 1px 0 rgba(255,255,255,0.2)`,
              }}
            >
              <Folder className="h-6 w-6 text-white" />
            </div>
            <motion.div
              className="opacity-0 group-hover:opacity-100 p-1.5 rounded-xl"
              initial={{ x: -4, opacity: 0 }}
              whileHover={{ x: 0, opacity: 1 }}
              style={{ background: `linear-gradient(135deg, ${palette.from}22, ${palette.to}22)` }}
            >
              <ArrowRight className="h-4 w-4" style={{ color: palette.from }} />
            </motion.div>
          </div>

          <h3 className="text-lg font-bold text-foreground mb-1.5 group-hover:text-gradient transition-all line-clamp-1">
            {workspace.name}
          </h3>

          {workspace.description && (
            <p className="text-sm text-muted-foreground line-clamp-2 leading-relaxed">
              {workspace.description}
            </p>
          )}

          {/* Stats pills — pushed to bottom */}
          <div className="flex flex-wrap gap-2 mt-auto pt-4">
            {[
              { icon: Calendar, label: formatDate(workspace.createdAt) },
              { icon: FileStack, label: `${workspace.fileCount} file${workspace.fileCount !== 1 ? 's' : ''}` },
              { icon: HardDrive, label: formatFileSize(workspace.totalSize) },
            ].map(({ icon: Icon, label }) => (
              <span
                key={label}
                className="flex items-center gap-1.5 px-2.5 py-1 rounded-xl text-xs font-medium text-muted-foreground"
                style={{
                  background: 'hsl(0,0%,96%)',
                  boxShadow: 'inset 0 1px 2px rgba(0,0,0,0.04)',
                }}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </span>
            ))}
          </div>
        </div>
      </div>
    </motion.button>
  );
}
