import { FileStatus } from '@/types/files';
import { cn } from '@/lib/utils';
import { Check, Clock, AlertCircle, Upload } from 'lucide-react';

interface FileStatusBadgeProps {
  status: FileStatus;
  className?: string;
}

const statusConfig: Record<FileStatus, { 
  label: string; 
  className: string; 
  icon: typeof Check 
}> = {
  pending: { 
    label: 'Pending', 
    className: 'status-pending',
    icon: Clock 
  },
  uploading: { 
    label: 'Uploading', 
    className: 'status-uploading',
    icon: Upload 
  },
  completed: { 
    label: 'Completed', 
    className: 'status-completed',
    icon: Check 
  },
  error: { 
    label: 'Error', 
    className: 'status-error',
    icon: AlertCircle 
  },
};

export function FileStatusBadge({ status, className }: FileStatusBadgeProps) {
  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <span className={cn('status-badge', config.className, className)}>
      <Icon className="h-3 w-3 mr-1" />
      {config.label}
    </span>
  );
}
