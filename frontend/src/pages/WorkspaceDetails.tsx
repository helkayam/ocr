import { useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Header } from '@/components/Header';
import { FileUploadArea } from '@/components/FileUploadArea';
import { FileUploadQueue } from '@/components/FileUploadQueue';
import { FileListTable } from '@/components/FileListTable';
import { FileFilters } from '@/components/FileFilters';
import { SearchBar } from '@/components/SearchBar';
import { MetadataModal } from '@/components/MetadataModal';
import { FileItem, FileType, UploadQueueItem } from '@/types/files';
import { toast } from 'sonner';
import { ArrowLeft } from 'lucide-react';
import { Button } from '@/components/ui/button';

// Mock data
const mockFiles: FileItem[] = [
  {
    id: '1',
    name: 'emergency-response-protocol-v2.pdf',
    type: 'pdf',
    size: 2450000,
    date: new Date('2024-03-10'),
    status: 'completed',
    metadata: {
      pages: 45,
      validationResults: [
        { type: 'success', message: 'PDF structure validated' },
        { type: 'success', message: 'All pages readable' },
      ],
    },
  },
  {
    id: '2',
    name: 'evacuation-routes.geojson',
    type: 'geojson',
    size: 890000,
    date: new Date('2024-03-08'),
    status: 'completed',
    metadata: {
      geoData: {
        type: 'FeatureCollection',
        features: 128,
        crs: 'EPSG:4326',
      },
      validationResults: [
        { type: 'success', message: 'GeoJSON structure valid' },
        { type: 'success', message: '128 features parsed' },
      ],
    },
  },
  {
    id: '3',
    name: 'field-operations-guide.docx',
    type: 'docx',
    size: 1200000,
    date: new Date('2024-03-05'),
    status: 'completed',
  },
  {
    id: '4',
    name: 'regional-boundaries.shp',
    type: 'shapefile',
    size: 4500000,
    date: new Date('2024-03-01'),
    status: 'error',
    error: 'Missing DBF component',
    metadata: {
      missingComponents: ['.dbf', '.prj'],
      validationResults: [
        { type: 'error', message: 'Missing required DBF file' },
        { type: 'warning', message: 'Missing projection file (.prj)' },
      ],
    },
  },
  {
    id: '5',
    name: 'incident-report-template.pdf',
    type: 'pdf',
    size: 560000,
    date: new Date('2024-02-28'),
    status: 'completed',
  },
  {
    id: '6',
    name: 'resource-allocation.geojson',
    type: 'geojson',
    size: 340000,
    date: new Date('2024-02-25'),
    status: 'pending',
  },
];

export default function WorkspaceDetails() {
  const { id } = useParams();
  const navigate = useNavigate();
  
  const [files, setFiles] = useState<FileItem[]>(mockFiles);
  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<FileType[]>([]);
  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const workspaceName = 'Emergency Response Plans';

  const handleFilesSelected = useCallback((newFiles: File[]) => {
    const queueItems: UploadQueueItem[] = newFiles.map(file => ({
      id: crypto.randomUUID(),
      file,
      progress: 0,
      status: 'uploading' as const,
    }));

    setUploadQueue(prev => [...prev, ...queueItems]);

    // Simulate upload progress
    queueItems.forEach(item => {
      let progress = 0;
      const interval = setInterval(() => {
        progress += Math.random() * 15;
        if (progress >= 100) {
          progress = 100;
          clearInterval(interval);
          
          // Simulate success or error
          const isSuccess = Math.random() > 0.2;
          
          setUploadQueue(prev =>
            prev.map(q =>
              q.id === item.id
                ? { ...q, progress: 100, status: isSuccess ? 'completed' : 'error', error: isSuccess ? undefined : 'Upload failed' }
                : q
            )
          );

          if (isSuccess) {
            toast.success(`${item.file.name} uploaded successfully`);
          } else {
            toast.error(`Failed to upload ${item.file.name}`);
          }
        } else {
          setUploadQueue(prev =>
            prev.map(q =>
              q.id === item.id ? { ...q, progress: Math.min(progress, 100) } : q
            )
          );
        }
      }, 200);
    });
  }, []);

  const handleRemoveFromQueue = useCallback((id: string) => {
    setUploadQueue(prev => prev.filter(item => item.id !== id));
  }, []);

  const handleTypeToggle = useCallback((type: FileType) => {
    setSelectedTypes(prev =>
      prev.includes(type)
        ? prev.filter(t => t !== type)
        : [...prev, type]
    );
  }, []);

  const handleClearFilters = useCallback(() => {
    setSelectedTypes([]);
  }, []);

  const handleViewDetails = useCallback((file: FileItem) => {
    setSelectedFile(file);
    setIsModalOpen(true);
  }, []);

  const handleDeleteFile = useCallback((id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id));
    toast.success('File deleted successfully');
  }, []);

  const filteredFiles = files.filter(file => {
    const matchesSearch = file.name.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesType = selectedTypes.length === 0 || selectedTypes.includes(file.type);
    return matchesSearch && matchesType;
  });

  return (
    <div className="min-h-screen bg-background">
      <Header workspaceName={workspaceName} />
      
      <main className="container mx-auto px-4 py-8">
        {/* Back Button */}
        <Button
          variant="ghost"
          size="sm"
          className="mb-6"
          onClick={() => navigate('/')}
        >
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Workspaces
        </Button>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
          {/* Upload Section */}
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
                <FileUploadQueue
                  items={uploadQueue}
                  onRemove={handleRemoveFromQueue}
                />
              </div>
            )}
          </div>

          {/* Files Section */}
          <div className="lg:col-span-2 space-y-6">
            <div className="animate-fade-in">
              <h2 className="text-xl font-semibold mb-4">Files</h2>
              
              <div className="space-y-4">
                <div className="flex flex-col sm:flex-row gap-4">
                  <SearchBar
                    value={searchQuery}
                    onChange={setSearchQuery}
                    placeholder="Search by file name..."
                    className="flex-1"
                  />
                </div>

                <FileFilters
                  selectedTypes={selectedTypes}
                  onTypeToggle={handleTypeToggle}
                  onClearFilters={handleClearFilters}
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
