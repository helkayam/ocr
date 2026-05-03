// ─── Core document types ─────────────────────────────────────────────────────

export type FileType = 'pdf' | 'docx' | 'geojson' | 'shapefile';
export type FileStatus = 'pending' | 'uploading' | 'completed' | 'error';

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
  download_url?: string;
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

// ─── NLP / Search ────────────────────────────────────────────────────────────

export interface SearchResult {
  chunk_id: string;
  file_id: string;
  filename: string;
  content: string;
  score: number;
}

export interface RagAnswer {
  query: string;
  answer: string;
}

// ─── Sensors ─────────────────────────────────────────────────────────────────

export type SensorType =
  | 'SMOKE'
  | 'FLOOD'
  | 'EARTHQUAKE'
  | 'CCTV'
  | 'TEMPERATURE'
  | 'GAS'
  | 'MEDICAL'
  | 'API';

export interface Sensor {
  sensor_id: string;
  workspace_id: string;
  name: string;
  sensor_type: SensorType;
  endpoint?: string;
  status: string;
  linked_file_id?: string;
}

// ─── Map / GIS ────────────────────────────────────────────────────────────────

export interface MapTag {
  tag_id: string;
  workspace_id: string;
  label: string;
  lat: number;
  lng: number;
  tag_type: string;
  color: string;
  file_id?: string;
}

export interface MapLayer {
  layer_id: string;
  file_id: string;
  filename: string;
  feature_count: number;
  geojson: object;
}

// ─── Readiness Report ────────────────────────────────────────────────────────

export interface ReadinessReport {
  workspace_id: string;
  score: number;
  covered: string[];
  gaps: string[];
  warnings: string[];
  total_files: number;
  total_sensors: number;
  file_types: string[];
  sensor_types: string[];
}
