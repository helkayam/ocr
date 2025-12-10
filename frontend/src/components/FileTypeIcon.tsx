import { FileText, FileType2, Map, Layers } from 'lucide-react';
import { FileType } from '@/types/files';
import { cn } from '@/lib/utils';

interface FileTypeIconProps {
  type: FileType;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const iconConfig: Record<FileType, { icon: typeof FileText; colorClass: string }> = {
  pdf: { icon: FileText, colorClass: 'text-red-500' },
  docx: { icon: FileType2, colorClass: 'text-blue-500' },
  geojson: { icon: Map, colorClass: 'text-green-500' },
  shapefile: { icon: Layers, colorClass: 'text-orange-500' },
};

const sizeConfig = {
  sm: 'h-4 w-4',
  md: 'h-5 w-5',
  lg: 'h-6 w-6',
};

export function FileTypeIcon({ type, size = 'md', className }: FileTypeIconProps) {
  const config = iconConfig[type];
  const Icon = config.icon;

  return (
    <div className={cn('flex items-center justify-center', className)}>
      <Icon className={cn(sizeConfig[size], config.colorClass)} />
    </div>
  );
}
