import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Header } from '@/components/Header';
import { api } from '@/lib/api';
import { Sensor, SensorType, FileItem } from '@/types/files';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import {
  ArrowLeft, Plus, Trash2, Link2, Cpu,
  Eye, Droplets, AlertTriangle, Thermometer, Wind, Heart, Globe
} from 'lucide-react';

const SENSOR_TYPES: { type: SensorType; label: string; icon: React.FC<any>; color: string }[] = [
  { type: 'SMOKE',       label: 'Smoke / Fire',    icon: Wind,        color: 'text-orange-400' },
  { type: 'FLOOD',       label: 'Flood / Water',   icon: Droplets,    color: 'text-blue-400' },
  { type: 'EARTHQUAKE',  label: 'Earthquake',      icon: AlertTriangle, color: 'text-red-400' },
  { type: 'CCTV',        label: 'CCTV Camera',     icon: Eye,         color: 'text-purple-400' },
  { type: 'TEMPERATURE', label: 'Temperature',     icon: Thermometer, color: 'text-yellow-400' },
  { type: 'GAS',         label: 'Gas / Chemical',  icon: Wind,        color: 'text-green-400' },
  { type: 'MEDICAL',     label: 'Medical',         icon: Heart,       color: 'text-pink-400' },
  { type: 'API',         label: 'External API',    icon: Globe,       color: 'text-sky-400' },
];

export default function SensorsView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: workspace } = useQuery({
    queryKey: ['workspace', id],
    queryFn: () => api.workspaces.get(id!),
    enabled: !!id,
  });

  const { data: sensors = [], refetch: refetchSensors } = useQuery({
    queryKey: ['sensors', id],
    queryFn: () => api.sensors.list(id!),
    enabled: !!id,
  });

  const { data: files = [] } = useQuery({
    queryKey: ['files', id],
    queryFn: () => api.files.list(id!),
    enabled: !!id,
  });

  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [sensorType, setSensorType] = useState<SensorType>('SMOKE');
  const [endpoint, setEndpoint] = useState('');
  const [linkTarget, setLinkTarget] = useState<string | null>(null);

  const createMutation = useMutation({
    mutationFn: api.sensors.create,
    onSuccess: () => {
      refetchSensors();
      setShowForm(false);
      setName('');
      setEndpoint('');
      toast.success('Sensor added');
    },
    onError: () => toast.error('Failed to add sensor'),
  });

  const deleteMutation = useMutation({
    mutationFn: api.sensors.delete,
    onSuccess: () => { refetchSensors(); toast.success('Sensor removed'); },
  });

  const linkMutation = useMutation({
    mutationFn: ({ sensorId, fileId }: { sensorId: string; fileId: string }) =>
      api.sensors.link(sensorId, fileId),
    onSuccess: () => { refetchSensors(); setLinkTarget(null); toast.success('Sensor linked to SOP'); },
    onError: () => toast.error('Failed to link sensor'),
  });

  const handleCreate = () => {
    if (!name.trim()) { toast.error('Sensor name is required'); return; }
    createMutation.mutate({
      workspace_id: id!,
      name: name.trim(),
      sensor_type: sensorType,
      endpoint: endpoint.trim() || undefined,
    });
  };

  const sopFiles = files.filter(f => f.type === 'pdf' || f.type === 'docx');

  return (
    <div className="min-h-screen bg-background">
      <Header workspaceName={workspace?.name} />

      <main className="container mx-auto px-4 py-8">
        <Button variant="ghost" size="sm" className="mb-6" onClick={() => navigate(`/workspace/${id}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Files
        </Button>

        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-2xl font-bold">Sensor Matrix</h1>
            <p className="text-muted-foreground text-sm mt-1">
              Connect hardware sensors and map them to SOPs for automated response.
            </p>
          </div>
          <Button onClick={() => setShowForm(!showForm)}>
            <Plus className="h-4 w-4 mr-2" />
            Add Sensor
          </Button>
        </div>

        {/* Add sensor form */}
        {showForm && (
          <div className="mb-6 p-5 rounded-xl bg-card border border-border animate-fade-in">
            <h3 className="text-sm font-semibold mb-4">New Sensor</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label className="text-xs">Sensor Name *</Label>
                <Input
                  value={name}
                  onChange={e => setName(e.target.value)}
                  placeholder="e.g. Lobby Smoke Detector #1"
                  className="bg-muted/50 h-9"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Endpoint (optional)</Label>
                <Input
                  value={endpoint}
                  onChange={e => setEndpoint(e.target.value)}
                  placeholder="192.168.1.100 or https://..."
                  className="bg-muted/50 h-9"
                />
              </div>
            </div>

            <div className="mt-4 space-y-1.5">
              <Label className="text-xs">Sensor Type</Label>
              <div className="flex flex-wrap gap-2">
                {SENSOR_TYPES.map(st => (
                  <button
                    key={st.type}
                    onClick={() => setSensorType(st.type)}
                    className={cn(
                      'flex items-center gap-1.5 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors',
                      sensorType === st.type
                        ? 'bg-primary/10 border-primary text-primary'
                        : 'border-border text-muted-foreground hover:bg-muted'
                    )}
                  >
                    <st.icon className={cn('h-3.5 w-3.5', sensorType === st.type ? 'text-primary' : st.color)} />
                    {st.label}
                  </button>
                ))}
              </div>
            </div>

            <div className="mt-4 flex gap-3">
              <Button size="sm" onClick={handleCreate} disabled={createMutation.isPending}>
                Add Sensor
              </Button>
              <Button size="sm" variant="ghost" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
            </div>
          </div>
        )}

        {/* Sensors grid */}
        {sensors.length === 0 ? (
          <div className="text-center py-20">
            <Cpu className="h-12 w-12 mx-auto text-muted-foreground/40 mb-4" />
            <p className="text-muted-foreground">No sensors yet. Add your first sensor above.</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {sensors.map(sensor => {
              const meta = SENSOR_TYPES.find(t => t.type === sensor.sensor_type) ?? SENSOR_TYPES[0];
              const linkedFile = files.find(f => f.id === sensor.linked_file_id);
              return (
                <div key={sensor.sensor_id} className="p-4 rounded-xl bg-card border border-border space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <div className="p-2 rounded-lg bg-muted shrink-0">
                        <meta.icon className={cn('h-4 w-4', meta.color)} />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate">{sensor.name}</p>
                        <p className="text-xs text-muted-foreground">{meta.label}</p>
                      </div>
                    </div>
                    <div className="flex items-center gap-1 shrink-0">
                      <span className={cn(
                        'text-xs px-2 py-0.5 rounded-full',
                        sensor.status === 'active'
                          ? 'bg-success/20 text-success'
                          : 'bg-muted text-muted-foreground'
                      )}>
                        {sensor.status}
                      </span>
                      <button onClick={() => deleteMutation.mutate(sensor.sensor_id)}>
                        <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive transition-colors" />
                      </button>
                    </div>
                  </div>

                  {sensor.endpoint && (
                    <p className="text-xs font-mono text-muted-foreground truncate">{sensor.endpoint}</p>
                  )}

                  <div className="pt-2 border-t border-border">
                    {linkedFile ? (
                      <div className="flex items-center gap-2">
                        <Link2 className="h-3.5 w-3.5 text-primary shrink-0" />
                        <span className="text-xs text-primary truncate">{linkedFile.name}</span>
                      </div>
                    ) : (
                      <div className="space-y-1.5">
                        <p className="text-xs text-muted-foreground">Link to SOP:</p>
                        {sopFiles.length === 0 ? (
                          <p className="text-xs text-muted-foreground italic">No SOP files uploaded</p>
                        ) : (
                          <select
                            className="w-full text-xs bg-muted border border-border rounded px-2 py-1 text-foreground"
                            defaultValue=""
                            onChange={e => {
                              if (e.target.value) {
                                linkMutation.mutate({ sensorId: sensor.sensor_id, fileId: e.target.value });
                              }
                            }}
                          >
                            <option value="">Select a file…</option>
                            {sopFiles.map(f => (
                              <option key={f.id} value={f.id}>{f.name}</option>
                            ))}
                          </select>
                        )}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
