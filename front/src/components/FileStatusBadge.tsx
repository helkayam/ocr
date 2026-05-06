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
  className: string;
  icon: typeof Check;
  spin?: boolean;
};

const uploadStatusConfig: Record<FileStatus, BadgeConfig> = {
  pending: { label: 'Pending', className: 'status-pending', icon: Clock },
  uploading: { label: 'Uploading', className: 'status-uploading', icon: Upload },
  completed: { label: 'Completed', className: 'status-completed', icon: Check },
  error: { label: 'Error', className: 'status-error', icon: AlertCircle },
};

const ragStatusConfig: Record<string, BadgeConfig> = {
  pending:       { label: 'RAG Queued',    className: 'status-uploading', icon: Loader2, spin: true },
  ocr_completed: { label: 'OCR Done',      className: 'status-uploading', icon: Loader2, spin: true },
  chunked:       { label: 'Chunking Done', className: 'status-uploading', icon: Loader2, spin: true },
  indexed:       { label: 'Indexed',       className: 'status-completed', icon: Check },
  error:         { label: 'Error',         className: 'status-error',     icon: AlertCircle },
};

export function FileStatusBadge({ status, processingStatus, className }: FileStatusBadgeProps) {
  const config =
    (processingStatus && ragStatusConfig[processingStatus]) ??
    uploadStatusConfig[status] ??
    uploadStatusConfig.completed;

  const Icon = config.icon;

  return (
    <span className={cn('status-badge', config.className, className)}>
      <Icon className={cn('h-3 w-3 mr-1', config.spin && 'animate-spin')} />
      {config.label}
    </span>
  );
}
