import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import { GeoFeature, GeoFeatureType } from '@/types/files';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Plus, Trash2, Shield, DoorOpen, Users, Flame, MapPin } from 'lucide-react';
import { toast } from 'sonner';
import { cn } from '@/lib/utils';

const FEATURE_TYPES: {
  type: GeoFeatureType;
  label: string;
  Icon: React.FC<{ className?: string }>;
  color: string;
}[] = [
  { type: 'exit',         label: 'Exit',        Icon: DoorOpen, color: 'text-green-400' },
  { type: 'shelter',      label: 'Shelter',     Icon: Shield,   color: 'text-blue-400' },
  { type: 'muster_point', label: 'Muster',      Icon: Users,    color: 'text-yellow-400' },
  { type: 'extinguisher', label: 'Extinguisher',Icon: Flame,    color: 'text-red-400' },
  { type: 'assembly',     label: 'Assembly',    Icon: MapPin,   color: 'text-purple-400' },
];

const FEATURE_MAP = Object.fromEntries(FEATURE_TYPES.map(f => [f.type, f]));

interface Props {
  workspaceId: string;
}

export function GeoFeatureManager({ workspaceId }: Props) {
  const qc = useQueryClient();
  const [showForm, setShowForm] = useState(false);
  const [featureType, setFeatureType] = useState<GeoFeatureType>('exit');
  const [label, setLabel] = useState('');
  const [lat, setLat] = useState('');
  const [lng, setLng] = useState('');
  const [floor, setFloor] = useState('');

  const { data: features = [] } = useQuery({
    queryKey: ['geo-features', workspaceId],
    queryFn: () => api.emergency.getFeatures(workspaceId),
    enabled: !!workspaceId,
  });

  const addMutation = useMutation({
    mutationFn: api.emergency.addFeature,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['geo-features', workspaceId] });
      setShowForm(false);
      setLabel(''); setLat(''); setLng(''); setFloor('');
      toast.success('Feature added');
    },
    onError: () => toast.error('Failed to add feature'),
  });

  const deleteMutation = useMutation({
    mutationFn: api.emergency.deleteFeature,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['geo-features', workspaceId] });
      toast.success('Feature removed');
    },
  });

  const handleAdd = () => {
    if (!label.trim() || !lat.trim() || !lng.trim()) {
      toast.error('Label and coordinates are required');
      return;
    }
    const latNum = parseFloat(lat);
    const lngNum = parseFloat(lng);
    if (isNaN(latNum) || isNaN(lngNum)) {
      toast.error('Coordinates must be valid numbers');
      return;
    }
    addMutation.mutate({
      workspace_id: workspaceId,
      feature_type: featureType,
      label: label.trim(),
      lat: latNum,
      lng: lngNum,
      floor: floor.trim() || undefined,
    });
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold">Emergency Features</h3>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 text-xs"
          onClick={() => setShowForm(v => !v)}
        >
          <Plus className="h-3 w-3 mr-1" />
          Add
        </Button>
      </div>

      {showForm && (
        <div className="p-3 rounded-lg bg-muted/50 border border-border space-y-2.5 text-xs">
          {/* Feature type selector */}
          <div className="flex flex-wrap gap-1.5">
            {FEATURE_TYPES.map(ft => (
              <button
                key={ft.type}
                onClick={() => setFeatureType(ft.type)}
                className={cn(
                  'flex items-center gap-1 px-2 py-1 rounded border text-xs transition-colors',
                  featureType === ft.type
                    ? 'bg-primary/10 border-primary text-primary'
                    : 'border-border text-muted-foreground hover:bg-muted'
                )}
              >
                <ft.Icon className={cn('h-3 w-3', featureType === ft.type ? 'text-primary' : ft.color)} />
                {ft.label}
              </button>
            ))}
          </div>
          <Input
            placeholder="Label (e.g. North Exit)"
            value={label}
            onChange={e => setLabel(e.target.value)}
            className="h-8 text-xs bg-background"
          />
          <div className="grid grid-cols-2 gap-2">
            <Input
              placeholder="Latitude"
              type="number"
              step="any"
              value={lat}
              onChange={e => setLat(e.target.value)}
              className="h-8 text-xs bg-background"
            />
            <Input
              placeholder="Longitude"
              type="number"
              step="any"
              value={lng}
              onChange={e => setLng(e.target.value)}
              className="h-8 text-xs bg-background"
            />
          </div>
          <Input
            placeholder="Floor (optional, e.g. B1, 2F)"
            value={floor}
            onChange={e => setFloor(e.target.value)}
            className="h-8 text-xs bg-background"
          />
          <div className="flex gap-2">
            <Button size="sm" className="h-7 text-xs" onClick={handleAdd} disabled={addMutation.isPending}>
              Add Feature
            </Button>
            <Button size="sm" variant="ghost" className="h-7 text-xs" onClick={() => setShowForm(false)}>
              Cancel
            </Button>
          </div>
        </div>
      )}

      {features.length === 0 ? (
        <p className="text-xs text-muted-foreground italic py-1">
          No emergency features registered.
        </p>
      ) : (
        <div className="space-y-1.5">
          {features.map(f => {
            const ft = FEATURE_MAP[f.feature_type as GeoFeatureType];
            const Icon = ft?.Icon ?? MapPin;
            const color = ft?.color ?? 'text-muted-foreground';
            return (
              <div
                key={f.feature_id}
                className="flex items-center justify-between px-2 py-2 rounded-lg bg-muted/30 border border-border"
              >
                <div className="flex items-center gap-2 min-w-0">
                  <Icon className={cn('h-3.5 w-3.5 shrink-0', color)} />
                  <div className="min-w-0">
                    <p className="text-xs font-medium truncate">{f.label}</p>
                    <p className="text-xs text-muted-foreground">
                      {f.lat.toFixed(4)}, {f.lng.toFixed(4)}
                      {f.floor ? ` · ${f.floor}` : ''}
                    </p>
                  </div>
                </div>
                <button
                  onClick={() => deleteMutation.mutate(f.feature_id)}
                  className="shrink-0 ml-2"
                >
                  <Trash2 className="h-3.5 w-3.5 text-muted-foreground hover:text-destructive transition-colors" />
                </button>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
