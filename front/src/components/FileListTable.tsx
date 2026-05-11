import { useState } from 'react';
import { FileItem, FileType } from '@/types/files';
import { FileTypeIcon } from './FileTypeIcon';
import { FileStatusBadge } from './FileStatusBadge';
import { Button } from '@/components/ui/button';
import { ArrowUpDown, ArrowUp, ArrowDown, MoreHorizontal, Trash2, Download, ScanSearch } from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { motion } from 'framer-motion';

interface FileListTableProps {
  files: FileItem[];
  onViewDetails: (file: FileItem) => void;
  onPreview?: (file: FileItem) => void;
  onDelete?: (id: string) => void;
}

type SortField = 'name' | 'type' | 'date' | 'size';
type SortDirection = 'asc' | 'desc';

function formatFileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(date: Date | null | undefined): string {
  if (!date || !(date instanceof Date) || isNaN(date.getTime())) return 'N/A';
  return new Intl.DateTimeFormat('en-US', {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

export function FileListTable({ files, onViewDetails, onPreview, onDelete }: FileListTableProps) {
  const [sortField, setSortField] = useState<SortField>('date');
  const [sortDirection, setSortDirection] = useState<SortDirection>('desc');

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDirection(prev => prev === 'asc' ? 'desc' : 'asc');
    } else {
      setSortField(field);
      setSortDirection('asc');
    }
  };

  const sortedFiles = [...files].sort((a, b) => {
    let comparison = 0;
    switch (sortField) {
      case 'name':
        comparison = a.name.localeCompare(b.name);
        break;
      case 'type':
        comparison = a.type.localeCompare(b.type);
        break;
      case 'date': {
        const aTime = a.date instanceof Date && !isNaN(a.date.getTime()) ? a.date.getTime() : 0;
        const bTime = b.date instanceof Date && !isNaN(b.date.getTime()) ? b.date.getTime() : 0;
        comparison = aTime - bTime;
        break;
      }
      case 'size':
        comparison = a.size - b.size;
        break;
    }
    return sortDirection === 'asc' ? comparison : -comparison;
  });

  const SortButton = ({ field, children }: { field: SortField; children: React.ReactNode }) => (
    <button
      onClick={() => handleSort(field)}
      className="flex items-center gap-1 text-gray-500 hover:text-gray-900 transition-colors group font-semibold"
    >
      {children}
      {sortField === field ? (
        sortDirection === 'asc'
          ? <ArrowUp className="h-3.5 w-3.5" style={{ color: 'hsl(0,84%,58%)' }} />
          : <ArrowDown className="h-3.5 w-3.5" style={{ color: 'hsl(0,84%,58%)' }} />
      ) : (
        <ArrowUpDown className="h-3.5 w-3.5 opacity-0 group-hover:opacity-40" />
      )}
    </button>
  );

  if (files.length === 0) {
    return (
      <div
        className="text-center py-16 rounded-3xl"
        style={{
          background: 'linear-gradient(135deg, hsl(0,0%,99%), hsl(0,0%,96%))',
          boxShadow: '0 4px 16px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.9)',
        }}
      >
        <p className="text-lg font-bold text-foreground">No files found</p>
        <p className="text-sm mt-1 text-muted-foreground">Upload files to get started</p>
      </div>
    );
  }

  return (
    <div
      className="rounded-3xl overflow-hidden bg-white border border-white/80"
      style={{ boxShadow: '0 6px 24px rgba(239,68,68,0.08), 0 2px 8px rgba(0,0,0,0.05), inset 0 1px 0 rgba(255,255,255,0.95)' }}
    >
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr
              style={{
                background: 'hsl(0,0%,98%)',
                borderBottom: '1px solid hsl(0,0%,90%)',
              }}
            >
              <th className="px-4 py-3.5 text-left text-xs font-bold text-gray-500 uppercase tracking-wider w-12">
                Type
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">
                <SortButton field="name">File Name</SortButton>
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-bold text-gray-500 uppercase tracking-wider hidden sm:table-cell">
                <SortButton field="type">Format</SortButton>
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-bold text-gray-500 uppercase tracking-wider hidden md:table-cell">
                <SortButton field="size">Size</SortButton>
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-bold text-gray-500 uppercase tracking-wider hidden lg:table-cell">
                <SortButton field="date">Date</SortButton>
              </th>
              <th className="px-4 py-3.5 text-left text-xs font-bold text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-4 py-3.5 text-right text-xs font-bold text-gray-500 uppercase tracking-wider w-24">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border/50">
            {sortedFiles.map((file, index) => (
              <motion.tr
                key={file.id}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: index * 0.04, type: 'spring', stiffness: 300 }}
                className="table-row-hover transition-colors duration-150"
              >
                <td className="px-4 py-3.5">
                  <FileTypeIcon type={file.type} size="md" />
                </td>
                <td className="px-4 py-3.5">
                  <span className="text-sm font-semibold text-foreground truncate block max-w-[200px] lg:max-w-[300px]">
                    {file.name}
                  </span>
                </td>
                <td className="px-4 py-3.5 hidden sm:table-cell">
                  <span className="text-xs font-bold uppercase px-2.5 py-1 rounded-xl text-muted-foreground"
                    style={{ background: 'hsl(0,0%,95%)' }}>
                    {file.type}
                  </span>
                </td>
                <td className="px-4 py-3.5 hidden md:table-cell">
                  <span className="text-sm text-muted-foreground font-medium">
                    {formatFileSize(file.size)}
                  </span>
                </td>
                <td className="px-4 py-3.5 hidden lg:table-cell">
                  <span className="text-sm text-muted-foreground">
                    {formatDate(file.date)}
                  </span>
                </td>
                <td className="px-4 py-3.5">
                  <FileStatusBadge status={file.status} processingStatus={file.processing_status} />
                </td>
                <td className="px-4 py-3.5">
                  <div className="flex items-center justify-end gap-1">
                    <motion.div whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.93 }}>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => onViewDetails(file)}
                        className="h-8 px-3 rounded-xl text-xs font-semibold hover:bg-primary/8"
                      >
                        <Download className="h-3.5 w-3.5 mr-1" />
                        <span className="hidden sm:inline">Details</span>
                      </Button>
                    </motion.div>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button variant="ghost" size="icon" className="h-8 w-8 rounded-xl">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end" className="w-40 rounded-2xl border-white/80"
                        style={{ boxShadow: '0 8px 24px rgba(0,0,0,0.10), inset 0 1px 0 rgba(255,255,255,0.9)' }}>
                        {file.type === 'pdf' && (
                          <DropdownMenuItem
                            disabled={!file.preview_url}
                            onClick={() => onPreview?.(file)}
                            className="rounded-xl"
                          >
                            <ScanSearch className="h-4 w-4 mr-2" />
                            Preview
                          </DropdownMenuItem>
                        )}
                        <DropdownMenuItem
                          disabled={!file.download_url}
                          onClick={() => {
                            if (!file.download_url) return;
                            const a = document.createElement('a');
                            a.href = file.download_url;
                            a.download = file.name;
                            document.body.appendChild(a);
                            a.click();
                            document.body.removeChild(a);
                          }}
                          className="rounded-xl"
                        >
                          <Download className="h-4 w-4 mr-2" />
                          Download
                        </DropdownMenuItem>
                        <DropdownMenuItem
                          className="text-destructive focus:text-destructive rounded-xl"
                          onClick={() => onDelete?.(file.id)}
                        >
                          <Trash2 className="h-4 w-4 mr-2" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                </td>
              </motion.tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
