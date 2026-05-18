import { useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { toast } from 'sonner';

/**
 * Shared hook for uploading a GeoJSON file into a workspace.
 * Used by both MapView (UploadLayerModal) and WorkspaceDetails (Upload Map tab).
 */
export function useGeoUpload(workspaceId: string) {
  const qc = useQueryClient();
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  const handleGeoUpload = async (file: File, geoCategory: string) => {
    setUploadProgress('Uploading...');
    try {
      const { upload_url, file_id } = await api.files.getUploadUrl({
        workspace_id: workspaceId,
        filename: file.name,
        content_type: 'application/geo+json',
        file_size: file.size,
      });
      await fetch(upload_url, {
        method: 'PUT',
        body: file,
        headers: { 'Content-Type': 'application/geo+json' },
      });
      await api.files.confirmUpload({
        file_id,
        workspace_id: workspaceId,
        filename: file.name,
        file_size: file.size,
        content_type: 'application/geo+json',
        geo_category: geoCategory,
      });
      setUploadProgress(null);
      // Invalidate all views that might show the new layer
      qc.invalidateQueries({ queryKey: ['map-layers', workspaceId] });
      qc.invalidateQueries({ queryKey: ['geo-features', workspaceId] });
      qc.invalidateQueries({ queryKey: ['files', workspaceId] });
      toast.success('GeoJSON layer uploaded');
    } catch {
      setUploadProgress(null);
      toast.error('Upload failed');
    }
  };

  return {
    handleGeoUpload,
    uploadProgress,
    isUploading: uploadProgress !== null,
  };
}
