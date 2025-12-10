export type FileType = 'pdf' | 'docx' | 'geojson' | 'shapefile';

export type FileStatus = 'pending' | 'uploading' | 'completed' | 'error';

export interface FileItem {
  id: string;
  name: string;
  type: FileType;
  size: number;
  date: Date;
  status: FileStatus;
  progress?: number;
  error?: string;
  metadata?: FileMetadata;
}

export interface FileMetadata {
  pages?: number;
  author?: string;
  createdAt?: Date;
  modifiedAt?: Date;
  validationResults?: ValidationResult[];
  missingComponents?: string[];
  previewUrl?: string;
  geoData?: GeoData;
}

export interface ValidationResult {
  type: 'success' | 'warning' | 'error';
  message: string;
}

export interface GeoData {
  type: string;
  features?: number;
  bounds?: [number, number, number, number];
  crs?: string;
}

export interface Workspace {
  id: string;
  name: string;
  description?: string;
  createdAt: Date;
  updatedAt: Date;
  fileCount: number;
  totalSize: number;
}

export interface UploadQueueItem {
  id: string;
  file: File;
  progress: number;
  status: FileStatus;
  error?: string;
}
