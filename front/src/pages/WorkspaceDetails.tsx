import { useState, useCallback, useRef, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import type { ImperativePanelHandle } from 'react-resizable-panels';
import { Header } from '@/components/Header';
import { FileUploadArea } from '@/components/FileUploadArea';
import { FileUploadQueue } from '@/components/FileUploadQueue';
import { FileListTable } from '@/components/FileListTable';
import { FileFilters } from '@/components/FileFilters';
import { SearchBar } from '@/components/SearchBar';
import { MetadataModal } from '@/components/MetadataModal';
import { PDFPreviewModal } from '@/components/PDFPreviewModal';
import { QueryBox } from '@/components/QueryBox';
import { SourcePreviewPanel } from '@/components/SourcePreviewPanel';
import { GeoLayerForm, GeoCategory } from '@/components/sim/GeoLayerForm';
import { useGeoUpload } from '@/hooks/useGeoUpload';
import {
  ResizablePanelGroup,
  ResizablePanel,
  ResizableHandle,
} from '@/components/ui/resizable';
import { CitedSource, FileItem, FileType, UploadQueueItem } from '@/types/files';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { ArrowLeft, Upload, X, FileText, Map } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { Dialog, DialogPortal, DialogTitle } from '@/components/ui/dialog';
import { cn } from '@/lib/utils';

export default function WorkspaceDetails() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // ── Remote data ────────────────────────────────────────────────────────────

  const { data: workspace } = useQuery({
    queryKey: ['workspace', id],
    queryFn: () => api.workspaces.get(id!),
    enabled: !!id,
  });

  const { data: files = [], isLoading: filesLoading, refetch: refetchFiles } = useQuery({
    queryKey: ['files', id],
    queryFn: () => api.files.list(id!),
    enabled: !!id,
    refetchInterval: (query) => {
      const data = query.state.data;
      if (!data) return false;
      const ACTIVE = new Set(['pending', 'ocr_completed', 'chunked']);
      return data.some(f => f.processing_status != null && ACTIVE.has(f.processing_status))
        ? 3_000
        : false;
    },
  });

  // ── Source-preview state ───────────────────────────────────────────────────

  const [activeSource, setActiveSource] = useState<CitedSource | null>(null);
  const previewPanelRef = useRef<ImperativePanelHandle>(null);

  // Programmatically open / collapse the right panel when activeSource changes
  useEffect(() => {
    if (activeSource) {
      previewPanelRef.current?.resize(40);
    } else {
      previewPanelRef.current?.collapse();
    }
  }, [activeSource]);

  const handleClosePreview = useCallback(() => {
    setActiveSource(null); // effect above will call collapse()
  }, []);

  // ── Upload state ───────────────────────────────────────────────────────────

  const [uploadQueue, setUploadQueue] = useState<UploadQueueItem[]>([]);
  const [uploadDrawerOpen, setUploadDrawerOpen] = useState(false);
  const [uploadTab, setUploadTab] = useState<'documents' | 'map'>('documents');
  const [geoCategory, setGeoCategory] = useState<GeoCategory>('buildings');
  const { handleGeoUpload, uploadProgress: geoProgress, isUploading: geoUploading } = useGeoUpload(id ?? '');

  // ── Filter / search state ──────────────────────────────────────────────────

  const [searchQuery, setSearchQuery] = useState('');
  const [selectedTypes, setSelectedTypes] = useState<FileType[]>([]);

  // ── Modal state ────────────────────────────────────────────────────────────

  const [selectedFile, setSelectedFile] = useState<FileItem | null>(null);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [previewFile, setPreviewFile] = useState<FileItem | null>(null);
  const [isPreviewOpen, setIsPreviewOpen] = useState(false);

  // ── Handlers ───────────────────────────────────────────────────────────────

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
            prev.map(q => q.id === item.id ? { ...q, progress: 30 } : q),
          );

          const putRes = await fetch(upload_url, { method: 'PUT', body: item.file });
          if (!putRes.ok) throw new Error('Storage upload failed');
          setUploadQueue(prev =>
            prev.map(q => q.id === item.id ? { ...q, progress: 75 } : q),
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
              q.id === item.id ? { ...q, progress: 100, status: 'completed' } : q,
            ),
          );
          toast.success(`${item.file.name} uploaded`);
          refetchFiles();
        } catch {
          setUploadQueue(prev =>
            prev.map(q =>
              q.id === item.id ? { ...q, status: 'error', error: 'Upload failed' } : q,
            ),
          );
          toast.error(`Failed to upload ${item.file.name}`);
        }
      }),
    );
  }, [id, refetchFiles]);

  const handleRemoveFromQueue = useCallback((queueId: string) => {
    setUploadQueue(prev => prev.filter(item => item.id !== queueId));
  }, []);

  const handleTypeToggle = useCallback((type: FileType) => {
    setSelectedTypes(prev =>
      prev.includes(type) ? prev.filter(t => t !== type) : [...prev, type],
    );
  }, []);

  const handleViewDetails = useCallback((file: FileItem) => {
    setSelectedFile(file);
    setIsModalOpen(true);
  }, []);

  const handlePreview = useCallback((file: FileItem) => {
    setPreviewFile(file);
    setIsPreviewOpen(true);
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

  // ── Render ─────────────────────────────────────────────────────────────────

  return (
    // h-screen + flex-col so the panel group fills exactly the viewport height
    <div className="h-screen flex flex-col overflow-hidden">
      <Header
        workspaceName={workspace?.name}
        onUploadClick={() => setUploadDrawerOpen(true)}
      />

      {/*
        flex-1 + min-h-0 lets the ResizablePanelGroup expand to fill the
        remaining height without overflowing the viewport.
      */}
      <div className="flex-1 min-h-0 overflow-hidden">
        <ResizablePanelGroup direction="horizontal" className="h-full">

          {/* ── Left panel: chat + file list ── */}
          <ResizablePanel
            defaultSize={100}
            minSize={35}
            style={{ transition: 'flex 180ms ease' }}
          >
            <div className="h-full overflow-y-auto">
              <div className="max-w-5xl mx-auto px-4 py-8">

                {/* Back button */}
                <motion.button
                  whileHover={{ x: -3 }}
                  whileTap={{ scale: 0.96 }}
                  transition={{ type: 'spring', stiffness: 400, damping: 20 }}
                  onClick={() => navigate('/')}
                  className="flex items-center gap-1.5 text-sm font-semibold text-muted-foreground hover:text-foreground transition-colors mb-7"
                >
                  <ArrowLeft className="h-4 w-4" />
                  Back to Workspaces
                </motion.button>

                {/* RAG query box */}
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.4 }}
                  className="mb-8"
                >
                  <QueryBox
                    workspaceId={id!}
                    onCitationClick={(source) => setActiveSource(source)}
                  />
                </motion.div>

                {/* File list */}
                <div className="space-y-5">
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.1, duration: 0.4 }}
                  >
                    <h2 className="text-xl font-extrabold mb-4 text-gradient">Files</h2>
                    <div
                      className="p-4 rounded-3xl bg-white border border-white/80 space-y-4"
                      style={{ boxShadow: '0 4px 16px rgba(239,68,68,0.06), inset 0 1px 0 rgba(255,255,255,0.95)' }}
                    >
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
                  </motion.div>

                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: 0.18, duration: 0.4 }}
                  >
                    {filesLoading ? (
                      <div className="space-y-2">
                        {[1, 2, 3, 4].map(i => (
                          <div
                            key={i}
                            className="h-14 rounded-2xl animate-pulse"
                            style={{ background: 'linear-gradient(135deg, hsl(0,0%,96%), hsl(0,0%,93%))' }}
                          />
                        ))}
                      </div>
                    ) : (
                      <FileListTable
                        files={filteredFiles}
                        onViewDetails={handleViewDetails}
                        onPreview={handlePreview}
                        onDelete={handleDeleteFile}
                      />
                    )}
                  </motion.div>
                </div>

              </div>
            </div>
          </ResizablePanel>

          {/* ── Resize handle — invisible until panel opens ── */}
          <ResizableHandle
            withHandle
            className={activeSource ? '' : 'opacity-0 pointer-events-none'}
          />

          {/* ── Right panel: source preview ── */}
          <ResizablePanel
            ref={previewPanelRef}
            defaultSize={0}
            collapsible
            collapsedSize={0}
            minSize={28}
            maxSize={62}
            style={{ transition: 'flex 180ms ease' }}
            onCollapse={() => setActiveSource(null)}
          >
            {activeSource && (
              <SourcePreviewPanel
                source={activeSource}
                onClose={handleClosePreview}
              />
            )}
          </ResizablePanel>

        </ResizablePanelGroup>
      </div>

      {/* ── Upload modal (portaled — unaffected by overflow-hidden) ── */}
      <Dialog open={uploadDrawerOpen} onOpenChange={setUploadDrawerOpen}>
        <DialogPortal forceMount>
          <AnimatePresence>
            {uploadDrawerOpen && (
              <>
                <DialogPrimitive.Overlay asChild forceMount>
                  <motion.div
                    key="upload-overlay"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                    exit={{ opacity: 0 }}
                    transition={{ duration: 0.18 }}
                    className="fixed inset-0 z-50 bg-black/65 backdrop-blur-sm"
                  />
                </DialogPrimitive.Overlay>

                <DialogPrimitive.Content
                  forceMount
                  className="fixed inset-0 z-50 flex items-center justify-center p-4 pointer-events-none focus:outline-none"
                >
                  <motion.div
                    key="upload-modal"
                    initial={{ opacity: 0, scale: 0.88, y: 20 }}
                    animate={{ opacity: 1, scale: 1, y: 0 }}
                    exit={{ opacity: 0, scale: 0.9, y: 12 }}
                    transition={{ type: 'spring', stiffness: 420, damping: 32 }}
                    className="relative w-full max-w-lg flex flex-col bg-white rounded-3xl overflow-hidden pointer-events-auto"
                    style={{
                      maxHeight: '90vh',
                      boxShadow: '0 24px 80px rgba(0,0,0,0.28), 0 8px 24px rgba(0,0,0,0.14)',
                    }}
                  >
                    <DialogTitle className="sr-only">Upload Files</DialogTitle>

                    {/* Header */}
                    <div
                      className="flex items-center justify-between px-6 py-5 border-b border-white/10 shrink-0"
                      style={{ background: 'linear-gradient(135deg, hsl(0,0%,10%) 0%, hsl(0,84%,32%) 100%)' }}
                    >
                      <div className="flex items-center gap-3">
                        <div className="p-2 rounded-xl bg-white/10">
                          <Upload className="h-5 w-5 text-white" />
                        </div>
                        <span className="font-bold text-white text-lg tracking-tight">Upload Files</span>
                      </div>
                      <motion.button
                        whileHover={{ scale: 1.1 }}
                        whileTap={{ scale: 0.9 }}
                        transition={{ type: 'spring', stiffness: 400, damping: 17 }}
                        onClick={() => setUploadDrawerOpen(false)}
                        className="p-2 rounded-xl text-white/70 hover:text-white hover:bg-white/10 transition-colors"
                      >
                        <X className="h-5 w-5" />
                      </motion.button>
                    </div>

                    {/* Tabs */}
                    <div className="flex border-b border-gray-100 shrink-0 bg-gray-50/60">
                      {([
                        { key: 'documents', label: 'Documents', icon: FileText },
                        { key: 'map',       label: 'Upload Map', icon: Map },
                      ] as const).map(({ key, label, icon: Icon }) => (
                        <button
                          key={key}
                          onClick={() => setUploadTab(key)}
                          className={cn(
                            'flex-1 flex items-center justify-center gap-2 py-3 text-sm font-semibold transition-all border-b-2',
                            uploadTab === key
                              ? 'border-red-500 text-red-600 bg-white'
                              : 'border-transparent text-gray-500 hover:text-gray-700'
                          )}
                        >
                          <Icon className="h-4 w-4" />
                          {label}
                        </button>
                      ))}
                    </div>

                    {/* Tab body */}
                    <div className="flex-1 overflow-y-auto p-6 space-y-4">
                      {uploadTab === 'documents' ? (
                        <>
                          <FileUploadArea
                            onFilesSelected={handleFilesSelected}
                            isUploading={uploadQueue.some(q => q.status === 'uploading')}
                          />
                          {uploadQueue.length > 0 && (
                            <div
                              className="p-4 rounded-3xl bg-white border border-gray-100"
                              style={{ boxShadow: '0 4px 16px rgba(239,68,68,0.08), inset 0 1px 0 rgba(255,255,255,0.95)' }}
                            >
                              <FileUploadQueue items={uploadQueue} onRemove={handleRemoveFromQueue} />
                            </div>
                          )}
                        </>
                      ) : (
                        <GeoLayerForm
                          geoCategory={geoCategory}
                          onGeoCategoryChange={setGeoCategory}
                          onFileSelect={file => handleGeoUpload(file, geoCategory)}
                          isUploading={geoUploading}
                          uploadProgress={geoProgress}
                        />
                      )}
                    </div>
                  </motion.div>
                </DialogPrimitive.Content>
              </>
            )}
          </AnimatePresence>
        </DialogPortal>
      </Dialog>

      <MetadataModal
        file={selectedFile}
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
      />

      <PDFPreviewModal
        file={previewFile}
        isOpen={isPreviewOpen}
        onClose={() => setIsPreviewOpen(false)}
      />
    </div>
  );
}
