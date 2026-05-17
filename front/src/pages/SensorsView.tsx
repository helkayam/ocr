import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Header } from '@/components/Header';
import { EmergencyResultCard } from '@/components/EmergencyResultCard';
import { api } from '@/lib/api';
import { Sensor, SensorType, EmergencySimResult } from '@/types/files';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import {
  ArrowLeft, Plus, Trash2, Link2, Cpu,
  AlertTriangle, Zap
} from 'lucide-react';

const SENSOR_TYPES: { type: SensorType; label: string; emoji: string; color: string }[] = [
  { type: 'SIREN',     label: 'Missile Alarm',         emoji: '🚨', color: 'text-red-400' },
  { type: 'TERRORIST', label: 'Terrorist Infiltration', emoji: '⚠️', color: 'text-purple-400' },
  { type: 'HAZMAT',    label: 'Hazardous Materials',   emoji: '☢️', color: 'text-orange-400' },
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

  // ── Create form state ──────────────────────────────────────────────────────
  const [showForm, setShowForm] = useState(false);
  const [name, setName] = useState('');
  const [sensorType, setSensorType] = useState<SensorType>('SIREN');
  const [endpoint, setEndpoint] = useState('');
  const [latStr, setLatStr] = useState('');
  const [lngStr, setLngStr] = useState('');
  const [linkTarget, setLinkTarget] = useState<string | null>(null);

  // ── Simulation state ───────────────────────────────────────────────────────
  const [activeSim, setActiveSim] = useState<string | null>(null);
  const [simResult, setSimResult] = useState<EmergencySimResult | null>(null);

  // ── Mutations ──────────────────────────────────────────────────────────────
  const createMutation = useMutation({
    mutationFn: api.sensors.create,
    onSuccess: () => {
      refetchSensors();
      setShowForm(false);
      setName(''); setEndpoint(''); setLatStr(''); setLngStr('');
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

  const simulateMutation = useMutation({
    mutationFn: (sensorId: string) =>
      api.emergency.simulate({
        workspace_id: id!,
        sensor_id: sensorId,
      }),
    onSuccess: data => {
      setSimResult(data);
      toast.success('Simulation complete');
    },
    onError: () => toast.error('Simulation failed — check server logs'),
  });

  // ── Handlers ───────────────────────────────────────────────────────────────
  const handleCreate = () => {
    if (!name.trim()) { toast.error('Sensor name is required'); return; }
    const lat = latStr ? parseFloat(latStr) : undefined;
    const lng = lngStr ? parseFloat(lngStr) : undefined;
    if ((latStr && isNaN(lat!)) || (lngStr && isNaN(lng!))) {
      toast.error('Coordinates must be valid numbers');
      return;
    }
    createMutation.mutate({
      workspace_id: id!,
      name: name.trim(),
      sensor_type: sensorType,
      endpoint: endpoint.trim() || undefined,
      lat,
      lng,
    });
  };

  const handleSimulate = (sensorId: string) => {
    setSimResult(null);
    setActiveSim(sensorId);
    simulateMutation.mutate(sensorId);
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
              Connect hardware sensors and simulate emergency responses from ingested protocols.
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
                  placeholder="e.g. Lobby Siren #1"
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
              <div className="space-y-1.5">
                <Label className="text-xs">Latitude (optional)</Label>
                <Input
                  type="number"
                  step="any"
                  value={latStr}
                  onChange={e => setLatStr(e.target.value)}
                  placeholder="e.g. 31.895"
                  className="bg-muted/50 h-9"
                />
              </div>
              <div className="space-y-1.5">
                <Label className="text-xs">Longitude (optional)</Label>
                <Input
                  type="number"
                  step="any"
                  value={lngStr}
                  onChange={e => setLngStr(e.target.value)}
                  placeholder="e.g. 35.015"
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
                    <span>{st.emoji}</span>
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
              const isSimulating = activeSim === sensor.sensor_id && simulateMutation.isPending;

              return (
                <div key={sensor.sensor_id} className="flex flex-col rounded-xl bg-card border border-border">
                  <div className="p-4 space-y-3 flex-1">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex items-center gap-2 min-w-0">
                        <div className="p-2 rounded-lg bg-muted shrink-0 text-xl leading-none">
                          {meta.emoji}
                        </div>
                        <div className="min-w-0">
                          <p className="text-sm font-medium truncate">{sensor.name}</p>
                          <p className={cn('text-xs', meta.color)}>{meta.label}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-1.5 shrink-0">
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

                    {sensor.lat != null && sensor.lng != null && (
                      <p className="text-xs text-muted-foreground font-mono">
                        📍 {sensor.lat.toFixed(4)}, {sensor.lng.toFixed(4)}
                      </p>
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

                  {/* Simulate section */}
                  <div className="px-4 pb-4">
                    <Button
                      variant="outline"
                      size="sm"
                      className="w-full h-8 text-xs border-orange-500/30 text-orange-400 hover:bg-orange-500/10"
                      onClick={() => handleSimulate(sensor.sensor_id)}
                      disabled={isSimulating}
                    >
                      {isSimulating ? (
                        <>
                          <span className="animate-spin mr-1.5">⏳</span>
                          Simulating...
                        </>
                      ) : (
                        <>
                          <AlertTriangle className="h-3.5 w-3.5 mr-1.5" />
                          Simulate Alert
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Simulation result panel */}
        {(simulateMutation.isPending || simResult) && (
          <div className="mt-8">
            <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-3">
              Simulation Result
            </h2>
            <div className="max-w-2xl">
              <EmergencyResultCard
                result={simResult}
                isLoading={simulateMutation.isPending}
              />
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
