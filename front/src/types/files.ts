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
  preview_url?: string;
  processing_status?: string;
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

export interface BBox {
  y_top: number;
  y_bottom: number;
  page_width: number;
  page_height: number;
}

export interface CitedSource {
  document_id: string;
  file_name: string;
  page_num: number;
  chunk_id: string;
  text_snippet: string;
  bbox: BBox | null;
}

export interface RagAnswer {
  query: string;
  answer: string;
  sources: CitedSource[];
}

// ─── Sensors ─────────────────────────────────────────────────────────────────

export type SensorType = 'SIREN' | 'TERRORIST' | 'HAZMAT';

export interface Sensor {
  sensor_id: string;
  workspace_id: string;
  name: string;
  sensor_type: SensorType;
  endpoint?: string;
  status: string;
  linked_file_id?: string;
  lat?: number;
  lng?: number;
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
  geo_category?: string; // 'cameras' | 'shelters' | 'buildings' | null
}

// ─── Emergency Simulation ─────────────────────────────────────────────────────

export type GeoFeatureType = 'shelter' | 'exit' | 'muster_point' | 'extinguisher' | 'assembly' | 'camera' | 'building';
export type AlertLevel = 'low' | 'medium' | 'high' | 'critical';

export interface GeoFeature {
  feature_id: string;
  workspace_id: string;
  feature_type: GeoFeatureType | string;
  label: string;
  lat: number;
  lng: number;
  floor?: string;
  metadata?: Record<string, unknown>;
  distance_m?: number;
  distance_display?: string;
}

export interface EmergencyIntent {
  action: string;
  target_type: GeoFeatureType | 'none';
  urgency: AlertLevel;
}

export interface EmergencySimResult {
  event_id: string;
  sensor: Sensor;
  alert_level: AlertLevel;
  rag_query: string;
  rag_answer: string;
  rag_sources: CitedSource[];
  intent: EmergencyIntent;
  nearest_feature: GeoFeature | null;
  directive: string;
}

export interface EmergencyEvent {
  event_id: string;
  workspace_id: string;
  sensor_name: string | null;
  sensor_type: string | null;
  alert_level: AlertLevel;
  intent_action: string | null;
  intent_target: string | null;
  intent_urgency: AlertLevel | null;
  nearest_feature_label: string | null;
  nearest_distance_m: number | null;
  directive: string | null;
  status: string;
  created_at: string;
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
