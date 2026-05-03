import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { Header } from '@/components/Header';
import { FileUploadArea } from '@/components/FileUploadArea';
import { FileUploadQueue } from '@/components/FileUploadQueue';
import { FileListTable } from '@/components/FileListTable';
import { FileFilters } from '@/components/FileFilters';
import { SearchBar } from '@/components/SearchBar';
import { MetadataModal } from '@/components/MetadataModal';
import { QueryBox } from '@/components/QueryBox';
import { FileItem, FileType, UploadQueueItem } from '@/types/files';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

export default function WorkspaceDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  const { data: workspace } = useQuery({
    queryKey: ['workspace', id],
    queryFn: () => api.workspaces.get(id!),
    enabled: !!id,
  });

  const { data: files = [], refetch: refetchFiles } = useQuery({
    queryKey: ['files', id],
    queryFn: () => api.files.list(id!),
    enabled: !!id,
  });

  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<FileType[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleFilesSelected = useCallback(async (newFiles: File[]) => {
    const queueItems: UploadQueueItem[] = newFiles.map(file => ({
      id: crypto.randomUUID(),
      file,
      progress: 0,
      status: 'uploading' as const,
    }));

    setUploadQueue(prev => [...prev, ...queueItems]);

    await Promise.all(
      queueItems.map(async item => {
        try {
          const { upload_url, file_id } = await api.files.getUploadUrl({
            workspace_id: id!,
            filename: item.file.name,
            content_type: item.file.type || 'application/octet-stream',
            file_size: item.file.size,
          });

          setUploadQueue(prev =>
            prev.map(q => q.id === item.id ? { ...q, progress: 30 } : q)
          );

          const putRes = await fetch(upload_url, { method: 'PUT', body: item.file });
          if (!putRes.ok) throw new Error('Storage upload failed');

          setUploadQueue(prev =>
            prev.map(q => q.id === item.id ? { ...q, progress: 75 } : q)
          );

          await api.files.confirmUpload({
            file_id,
            workspace_id: id!,
            filename: item.file.name,
            file_size: item.file.size,
            content_type: item.file.type || 'application/octet-stream',
          });

          setUploadQueue(prev =>
            prev.map(q =>
              q.id === item.id ? { ...q, progress: 100, status: 'completed' } : q
            )
          );

          toast.success(`${item.file.name} uploaded`);
          refetchFiles();
        } catch {
          setUploadQueue(prev =>
            prev.map(q =>
              q.id === item.id ? { ...q, status: 'error', error: 'Upload failed' } : q
            )
          );
          toast.error(`Failed to upload ${item.file.name}`);
        }
      })
    );
  }, [id, refetchFiles]);

  const handleRemoveFromQueue = useCallback((queueId: string) => {
    setUploadQueue(prev => prev.filter(item => item.id !== queueId));
  }, []);

  const handleTypeToggle = useCallback((type: FileType) => {
    setSelectedTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type]
    );
  }, []);

  const handleViewDetails = useCallback((file: FileItem) => {
    setSelectedFile(file);
    setIsModalOpen(true);
  }, []);

  const handleDeleteFile = useCallback(async (fileId: string) => {
    try {
      await api.files.delete(fileId);
      toast.success('File deleted');
      refetchFiles();
    } catch {
      toast.error('Failed to delete file');
    }
  }, [refetchFiles]);

  const filteredFiles = files.filter(file => {
    const matchesSearch = file.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = selectedTypes.length === 0 || selectedTypes.includes(file.type);
    return matchesSearch && matchesType;
  });

  return (
    <div className="min-h-screen bg-background">
      <Header workspaceName={workspace?.name} />

      <main className="container mx-auto px-4 py-8">
        <Button variant="ghost" size="sm" className="mb-6" onClick={() => navigate('/')}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Workspaces
        </Button>

        {/* SOP Search — full width at the top */}
        <div className="mb-8 animate-fade-in">
          <QueryBox workspaceId={id!} />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Upload Column */}
          <div className="lg:col-span-1 space-y-6">
            <div className="animate-fade-in">
              <h2 className="text-xl font-semibold mb-4">Upload Files</h2>
              <FileUploadArea
                onFilesSelected={handleFilesSelected}
                isUploading={uploadQueue.some(q => q.status === 'uploading')}
              />
            </div>

            {uploadQueue.length > 0 && (
              <div className="animate-fade-in">
                <FileUploadQueue items={uploadQueue} onRemove={handleRemoveFromQueue} />
              </div>
            )}
          </div>

          {/* Files Column */}
          <div className="lg:col-span-2 space-y-6">
            <div className="animate-fade-in">
              <h2 className="text-xl font-semibold mb-4">Files</h2>
              <div className="space-y-4">
                <SearchBar
                  value={searchQuery}
                  onChange={setSearchQuery}
                  placeholder="Search by file name..."
                  className="w-full"
                />
                <FileFilters
                  selectedTypes={selectedTypes}
                  onTypeToggle={handleTypeToggle}
                  onClearFilters={() => setSelectedTypes([])}
                />
              </div>
            </div>

            <div className="animate-fade-in" style={{ animationDelay: '100ms' }}>
              <FileListTable
                files={filteredFiles}
                onViewDetails={handleViewDetails}
                onDelete={handleDeleteFile}
              />
            </div>
          </div>
        </div>
      </main>

      <MetadataModal
        file={selectedFile}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />
    </div>
  );
}
