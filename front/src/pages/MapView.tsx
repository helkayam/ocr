import { useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Header } from '@/components/Header';
import { MapComponent } from '@/components/MapComponent';
import { api } from '@/lib/api';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { cn } from '@/lib/utils';
import { toast } from 'sonner';
import { ArrowLeft, MapPin, Layers, Tag, Trash2, Plus, ChevronDown } from 'lucide-react';
import { LAYER_COLORS } from '@/components/MapComponent';

const TAG_COLORS = [
  { label: 'Red',    value: '#ef4444' },
  { label: 'Blue',   value: '#3b82f6' },
  { label: 'Green',  value: '#22c55e' },
  { label: 'Yellow', value: '#eab308' },
  { label: 'Purple', value: '#a855f7' },
];

const TAG_TYPES = ['point', 'assembly', 'hazard', 'exit', 'hydrant', 'camera'];

export default function MapView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: workspace } = useQuery({
    queryKey: ['workspace', id],
    queryFn: () => api.workspaces.get(id!),
    enabled: !!id,
  });

  const { data: layers = [] } = useQuery({
    queryKey: ['map-layers', id],
    queryFn: () => api.map.getLayers(id!),
    enabled: !!id,
  });

  const { data: tags = [], refetch: refetchTags } = useQuery({
    queryKey: ['map-tags', id],
    queryFn: () => api.map.getTags(id!),
    enabled: !!id,
  });

  const [tagMode, setTagMode] = useState(false);
  const [pendingCoord, setPendingCoord] = useState<{ lat: number; lng: number } | null>(null);
  const [tagLabel, setTagLabel] = useState('');
  const [tagType, setTagType] = useState('point');
  const [tagColor, setTagColor] = useState('#ef4444');

  // Sidebar ↔ map sync
  const [selectedLayerIdx, setSelectedLayerIdx] = useState<number | null>(null);
  const [expandedLayerId, setExpandedLayerId] = useState<string | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<object | null>(null);

  const addTagMutation = useMutation({
    mutationFn: api.map.addTag,
    onSuccess: () => {
      refetchTags();
      setPendingCoord(null);
      setTagLabel('');
      toast.success('Tag added');
    },
  });

  const deleteTagMutation = useMutation({
    mutationFn: api.map.deleteTag,
    onSuccess: () => {
      refetchTags();
      toast.success('Tag deleted');
    },
  });

  const handleMapClick = (lat: number, lng: number) => {
    setPendingCoord({ lat, lng });
  };

  const handleAddTag = () => {
    if (!pendingCoord || !tagLabel.trim()) return;
    addTagMutation.mutate({
      workspace_id: id!,
      label: tagLabel.trim(),
      lat: pendingCoord.lat,
      lng: pendingCoord.lng,
      tag_type: tagType,
      color: tagColor,
    });
  };

  return (
    <div className="min-h-screen bg-background flex flex-col">
      <Header workspaceName={workspace?.name} />

      <main className="container mx-auto px-4 py-6 flex-1 flex flex-col gap-6">
        <Button variant="ghost" size="sm" className="self-start" onClick={() => navigate(`/workspace/${id}`)}>
          <ArrowLeft className="h-4 w-4 mr-2" />
          Back to Files
        </Button>

        <div className="flex flex-col lg:flex-row gap-6 flex-1">
          {/* Map */}
          <div className="flex-1 min-h-[500px] animate-fade-in">
            <MapComponent
              layers={layers}
              tags={tags}
              tagMode={tagMode}
              onMapClick={handleMapClick}
              onTagDelete={tid => deleteTagMutation.mutate(tid)}
              selectedLayerIndex={selectedLayerIdx}
              selectedFeature={selectedFeature}
              className="h-full min-h-[500px]"
            />
          </div>

          {/* Sidebar */}
          <div className="w-full lg:w-80 space-y-4 animate-fade-in">
            {/* Tag mode toggle */}
            <div className="p-4 rounded-xl bg-card border border-border">
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-semibold flex items-center gap-2">
                  <Tag className="h-4 w-4 text-primary" />
                  Tag Points
                </h3>
                <Button
                  size="sm"
                  variant={tagMode ? 'default' : 'outline'}
                  onClick={() => { setTagMode(!tagMode); setPendingCoord(null); }}
                >
                  {tagMode ? 'Cancel' : <><Plus className="h-3.5 w-3.5 mr-1" />Add Tag</>}
                </Button>
              </div>

              {pendingCoord && tagMode && (
                <div className="space-y-3 pt-2 border-t border-border">
                  <p className="text-xs text-muted-foreground">
                    📍 {pendingCoord.lat.toFixed(5)}, {pendingCoord.lng.toFixed(5)}
                  </p>
                  <div className="space-y-1">
                    <Label className="text-xs">Label</Label>
                    <Input
                      value={tagLabel}
                      onChange={e => setTagLabel(e.target.value)}
                      placeholder="e.g. Assembly Point A"
                      className="bg-muted/50 h-8 text-sm"
                    />
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Type</Label>
                    <div className="flex flex-wrap gap-1">
                      {TAG_TYPES.map(t => (
                        <button
                          key={t}
                          onClick={() => setTagType(t)}
                          className={cn(
                            'px-2 py-0.5 rounded text-xs border transition-colors capitalize',
                            tagType === t
                              ? 'bg-primary/10 border-primary text-primary'
                              : 'border-border text-muted-foreground hover:bg-muted'
                          )}
                        >
                          {t}
                        </button>
                      ))}
                    </div>
                  </div>
                  <div className="space-y-1">
                    <Label className="text-xs">Color</Label>
                    <div className="flex gap-2">
                      {TAG_COLORS.map(c => (
                        <button
                          key={c.value}
                          onClick={() => setTagColor(c.value)}
                          title={c.label}
                          className={cn(
                            'w-6 h-6 rounded-full border-2 transition-transform',
                            tagColor === c.value ? 'border-white scale-125' : 'border-transparent'
                          )}
                          style={{ background: c.value }}
                        />
                      ))}
                    </div>
                  </div>
                  <Button
                    size="sm"
                    className="w-full"
                    onClick={handleAddTag}
                    disabled={!tagLabel.trim() || addTagMutation.isPending}
                  >
                    <MapPin className="h-3.5 w-3.5 mr-1.5" />
                    Save Tag
                  </Button>
                </div>
              )}
            </div>

            {/* Layers */}
            <div className="p-4 rounded-xl bg-card border border-border">
              <h3 className="text-sm font-semibold flex items-center gap-2 mb-3">
                <Layers className="h-4 w-4 text-primary" />
                GIS Layers
                <span className="ml-auto text-xs text-muted-foreground">{layers.length}</span>
              </h3>
              {layers.length === 0 ? (
                <p className="text-xs text-muted-foreground">
                  No GIS layers yet. Upload a GeoJSON file in the Files tab.
                </p>
              ) : (
                <ul className="space-y-1">
                  {layers.map((layer, i) => {
                    const isExpanded = expandedLayerId === layer.layer_id;
                    const isSelected = selectedLayerIdx === i;
                    const features = (layer.geojson as any)?.features ?? [];
                    return (
                      <li key={layer.layer_id}>
                        {/* Layer header row — click to zoom + expand */}
                        <button
                          onClick={() => {
                            setSelectedLayerIdx(i);
                            setSelectedFeature(null);
                            setExpandedLayerId(isExpanded ? null : layer.layer_id);
                          }}
                          className={cn(
                            'w-full flex items-center gap-2 px-2 py-1.5 rounded-lg transition-colors text-left',
                            isSelected
                              ? 'bg-primary/10 text-primary'
                              : 'hover:bg-muted/50 text-foreground'
                          )}
                        >
                          <div
                            className="w-3 h-3 rounded-full shrink-0"
                            style={{ background: LAYER_COLORS[i % LAYER_COLORS.length] }}
                          />
                          <span className="text-xs truncate flex-1">{layer.filename}</span>
                          <span className="text-xs text-muted-foreground shrink-0 mr-1">
                            {layer.feature_count}
                          </span>
                          {features.length > 0 && (
                            <ChevronDown
                              className={cn(
                                'h-3.5 w-3.5 text-muted-foreground shrink-0 transition-transform duration-200',
                                isExpanded && 'rotate-180'
                              )}
                            />
                          )}
                        </button>

                        {/* Feature sub-list */}
                        {isExpanded && features.length > 0 && (
                          <ul className="ml-5 mt-0.5 mb-1 border-l border-border pl-2 space-y-0.5">
                            {features.slice(0, 12).map((feat: any, fi: number) => {
                              const p = feat.properties ?? {};
                              const fname =
                                p.name  ?? p.NAME  ??
                                p.label ?? p.LABEL ??
                                p.title ?? p.TITLE ??
                                p.id    ?? p.ID    ?? `Feature ${fi + 1}`;
                              return (
                                <li key={fi}>
                                  <button
                                    onClick={() => setSelectedFeature(feat)}
                                    className="w-full text-left text-xs py-0.5 px-1 rounded hover:bg-muted/50 text-muted-foreground hover:text-foreground transition-colors truncate"
                                  >
                                    {String(fname)}
                                  </button>
                                </li>
                              );
                            })}
                            {features.length > 12 && (
                              <li className="text-xs text-muted-foreground px-1 py-0.5">
                                +{features.length - 12} more
                              </li>
                            )}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                </ul>
              )}
            </div>

            {/* Tags list */}
            <div className="p-4 rounded-xl bg-card border border-border">
              <h3 className="text-sm font-semibold flex items-center gap-2 mb-3">
                <MapPin className="h-4 w-4 text-primary" />
                Tags
                <span className="ml-auto text-xs text-muted-foreground">{tags.length}</span>
              </h3>
              {tags.length === 0 ? (
                <p className="text-xs text-muted-foreground">No tags yet. Enable "Add Tag" and click the map.</p>
              ) : (
                <ul className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
                  {tags.map(tag => (
                    <li key={tag.tag_id} className="flex items-center gap-2 group">
                      <div
                        className="w-3 h-3 rounded-full shrink-0"
                        style={{ background: tag.color }}
                      />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium truncate">{tag.label}</p>
                        <p className="text-xs text-muted-foreground capitalize">{tag.tag_type}</p>
                      </div>
                      <button
                        onClick={() => deleteTagMutation.mutate(tag.tag_id)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity"
                        title="Delete"
                      >
                        <Trash2 className="h-3.5 w-3.5 text-destructive" />
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
