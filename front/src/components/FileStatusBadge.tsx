import { FileStatus } from '@/types/files';
import { cn } from '@/lib/utils';
import { Check, Clock, AlertCircle, Upload, Loader2 } from 'lucide-react';

interface FileStatusBadgeProps {
  status: FileStatus;
  processingStatus?: string;
  className?: string;
}

type BadgeConfig = {
  label: string;
  style: React.CSSProperties;
  icon: typeof Check;
  spin?: boolean;
};

const uploadStatusConfig: Record<FileStatus, BadgeConfig> = {
  pending: {
    label: 'Pending',
    style: { background: 'hsl(38,92%,95%)', color: 'hsl(38,80%,40%)', border: '1px solid hsl(38,80%,82%)' },
    icon: Clock,
  },
  uploading: {
    label: 'Uploading',
    style: {
      background: 'linear-gradient(135deg, hsl(0,84%,58%), hsl(0,84%,45%))',
      color: 'white',
      boxShadow: '0 2px 8px rgba(239,68,68,0.3)',
    },
    icon: Upload,
    spin: false,
  },
  completed: {
    label: 'Completed',
    style: {
      background: 'linear-gradient(135deg, hsl(158,64%,48%), hsl(158,64%,40%))',
      color: 'white',
      boxShadow: '0 2px 8px rgba(52,211,153,0.3)',
    },
    icon: Check,
  },
  error: {
    label: 'Error',
    style: {
      background: 'linear-gradient(135deg, hsl(0,84%,60%), hsl(0,84%,52%))',
      color: 'white',
      boxShadow: '0 2px 8px rgba(239,68,68,0.3)',
    },
    icon: AlertCircle,
  },
};

const ragStatusConfig: Record<string, BadgeConfig> = {
  pending: {
    label: 'RAG Queued',
    style: {
      background: 'linear-gradient(135deg, hsl(0,0%,22%), hsl(0,0%,12%))',
      color: 'white',
      boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
    },
    icon: Loader2,
    spin: true,
  },
  ocr_completed: {
    label: 'OCR Done',
    style: {
      background: 'linear-gradient(135deg, hsl(30,80%,52%), hsl(20,78%,44%))',
      color: 'white',
      boxShadow: '0 2px 8px rgba(200,100,40,0.25)',
    },
    icon: Loader2,
    spin: true,
  },
  chunked: {
    label: 'Chunking Done',
    style: {
      background: 'linear-gradient(135deg, hsl(0,0%,20%), hsl(0,84%,36%))',
      color: 'white',
      boxShadow: '0 2px 8px rgba(0,0,0,0.2)',
    },
    icon: Loader2,
    spin: true,
  },
  indexed: {
    label: 'Indexed',
    style: {
      background: 'linear-gradient(135deg, hsl(158,64%,48%), hsl(158,64%,40%))',
      color: 'white',
      boxShadow: '0 2px 8px rgba(52,211,153,0.3)',
    },
    icon: Check,
  },
  error: {
    label: 'Error',
    style: {
      background: 'linear-gradient(135deg, hsl(0,84%,60%), hsl(0,84%,52%))',
      color: 'white',
      boxShadow: '0 2px 8px rgba(239,68,68,0.3)',
    },
    icon: AlertCircle,
  },
};

export function FileStatusBadge({ status, processingStatus, className }: FileStatusBadgeProps) {
  const config =
    (processingStatus && ragStatusConfig[processingStatus]) ??
    uploadStatusConfig[status] ??
    uploadStatusConfig.completed;

  const Icon = config.icon;

  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 px-2.5 py-1 rounded-2xl text-xs font-semibold whitespace-nowrap',
        className
      )}
      style={config.style}
    >
      <Icon className={cn('h-3 w-3', config.spin && 'animate-spin')} />
      {config.label}
    </span>
  );
}
