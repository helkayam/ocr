import {
  FileItem,
  MapLayer,
  MapTag,
  RagAnswer,
  ReadinessReport,
  SearchResult,
  Sensor,
  Workspace,
} from '@/types/files';

const BASE = (import.meta.env.VITE_API_URL as string) || 'http://localhost:8000';

/** Recursively convert ISO date strings to Date objects. */
function parseDates<T>(obj: T): T {
  if (obj === null || typeof obj !== 'object') return obj;
  if (Array.isArray(obj)) return obj.map(parseDates) as unknown as T;
  const r = { ...(obj as Record<string, unknown>) };
  for (const key of ['createdAt', 'updatedAt', 'date']) {
    if (typeof r[key] === 'string' && r[key]) {
      const d = new Date(r[key] as string);
      if (!isNaN(d.getTime())) r[key] = d;
    }
  }
  for (const key of Object.keys(r)) {
    if (r[key] !== null && typeof r[key] === 'object') {
      r[key] = parseDates(r[key]);
    }
  }
  return r as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, init);
  if (!res.ok) {
    const msg = await res.text().catch(() => res.statusText);
    throw new Error(`${res.status}: ${msg}`);
  }
  if (res.status === 204) return undefined as T;
  const json = await res.json();
  return parseDates(json) as T;
}

function post<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
}

function del(path: string): Promise<void> {
  return request<void>(path, { method: 'DELETE' });
}

// ─── API surface ──────────────────────────────────────────────────────────────

export const api = {
  workspaces: {
    list: (): Promise<Workspace[]> => request('/workspaces'),
    get: (id: string): Promise<Workspace> => request(`/workspaces/${id}`),
    create: (body: { name: string; description?: string }): Promise<Workspace> =>
      post('/workspaces', body),
  },

  files: {
    list: (workspaceId: string): Promise<FileItem[]> =>
      request(`/files?workspace_id=${encodeURIComponent(workspaceId)}`),
    getUploadUrl: (body: {
      workspace_id: string;
      filename: string;
      content_type: string;
      file_size: number;
    }): Promise<{ upload_url: string; file_id: string; expires_in: number }> =>
      post('/files/upload-url', body),
    confirmUpload: (body: {
      file_id: string;
      workspace_id: string;
      filename: string;
      file_size: number;
      content_type: string;
    }): Promise<{ file: FileItem }> => post('/files/confirm-upload', body),
    getStatus: (fileId: string): Promise<{ file_id: string; processing_status: string }> =>
      request(`/files/${fileId}/status`),
    delete: (fileId: string): Promise<void> => del(`/documents/${fileId}`),
  },

  search: {
    query: (body: {
      workspace_id: string;
      query: string;
      top_k?: number;
    }): Promise<SearchResult[]> => post('/search', body),
  },

  rag: {
    query: (body: { query: string; top_k?: number }): Promise<RagAnswer> =>
      post('/query/', body),
  },

  sensors: {
    list: (workspaceId: string): Promise<Sensor[]> =>
      request(`/sensors?workspace_id=${encodeURIComponent(workspaceId)}`),
    create: (body: {
      workspace_id: string;
      name: string;
      sensor_type: string;
      endpoint?: string;
    }): Promise<Sensor> => post('/sensors', body),
    delete: (sensorId: string): Promise<void> => del(`/sensors/${sensorId}`),
    link: (sensorId: string, fileId: string): Promise<Sensor> =>
      post(`/sensors/${sensorId}/link`, { file_id: fileId }),
  },

  map: {
    getLayers: (workspaceId: string): Promise<MapLayer[]> =>
      request(`/map/layers/${workspaceId}`),
    getTags: (workspaceId: string): Promise<MapTag[]> =>
      request(`/map/tags/${workspaceId}`),
    addTag: (body: {
      workspace_id: string;
      label: string;
      lat: number;
      lng: number;
      tag_type?: string;
      color?: string;
      file_id?: string;
    }): Promise<MapTag> => post('/map/tags', body),
    deleteTag: (tagId: string): Promise<void> => del(`/map/tags/${tagId}`),
  },

  report: {
    get: (workspaceId: string): Promise<ReadinessReport> =>
      request(`/report/${workspaceId}`),
  },
};
