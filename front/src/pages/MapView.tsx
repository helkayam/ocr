/**
 * MapView — Full-screen tactical map with floating action dock,
 * simulation overlay, and slide-in control panels.
 *
 * Simulation flow (strict two-step):
 *   1. User selects a sensor  → stages it, opens SimulationOverlay in "origin" phase
 *   2. User clicks the map    → sets userEvacOrigin
 *   3. User clicks "Run"      → mutation fires with origin_lat/lng
 *   Routing from sensor coords is impossible; origin is always user-supplied.
 */
import { useState, useMemo, useRef } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery, useMutation } from '@tanstack/react-query';
import { useGeoUpload } from '@/hooks/useGeoUpload';
import { AnimatePresence, motion } from 'framer-motion';
import type { Feature, Geometry, GeoJsonProperties } from 'geojson';
import { Header } from '@/components/Header';
import { MapComponent } from '@/components/MapComponent';
import { api } from '@/lib/api';
import { toast } from 'sonner';
import { ArrowLeft, Plus, Upload, Cpu, Zap, Crosshair, MapPin, X } from 'lucide-react';
import { Sensor, SensorType, EmergencySimResult, StreamPhase } from '@/types/files';
import { SimulationOverlay } from '@/components/sim/SimulationOverlay';
import { AlarmWidget } from '@/components/sim/AlarmWidget';
import { AddEntityPanel } from '@/components/sim/AddEntityPanel';
import { ControlCenterDrawer } from '@/components/sim/ControlCenterDrawer';
import { UploadLayerModal } from '@/components/sim/UploadLayerModal';
import { cn } from '@/lib/utils';

// ─── Types ────────────────────────────────────────────────────────────────────

type EntityType = 'Sensor' | 'Camera' | 'Shelter' | 'Building';
type GeoCategory = 'cameras' | 'shelters' | 'buildings';

const ENTITY_TO_FEATURE: Record<EntityType, string> = {
  Camera:   'camera',
  Shelter:  'shelter',
  Building: 'building',
  Sensor:   'shelter',
};

// ─── Floating Dock ────────────────────────────────────────────────────────────

interface DockButtonProps {
  icon: React.ElementType;
  label: string;
  active?: boolean;
  prominent?: boolean;
  pulse?: boolean;
  onClick: () => void;
}

function DockButton({ icon: Icon, label, active, prominent, pulse, onClick }: DockButtonProps) {
  return (
    <motion.button
      whileHover={{ scale: 1.08 }}
      whileTap={{ scale: 0.93 }}
      transition={{ type: 'spring', stiffness: 400, damping: 17 }}
      onClick={onClick}
      title={label}
      className={cn(
        'flex flex-col items-center gap-1 w-14 py-3 rounded-2xl text-xs font-bold transition-all select-none',
        prominent
          ? 'text-white'
          : active
          ? 'bg-primary/15 text-primary border border-primary/30'
          : 'bg-card/90 text-muted-foreground hover:text-foreground border border-border/60 hover:bg-card',
        pulse && 'animate-pulse',
      )}
      style={prominent ? {
        background: 'linear-gradient(160deg, hsl(0,84%,55%) 0%, hsl(0,84%,38%) 100%)',
        boxShadow: '0 4px 24px rgba(239,68,68,0.55), inset 0 1px 0 rgba(255,255,255,0.2)',
      } : undefined}
    >
      <Icon className={cn('h-5 w-5', prominent && 'drop-shadow')} />
      <span className="leading-none text-[10px] uppercase tracking-wide">{label}</span>
    </motion.button>
  );
}

// ─── Component ────────────────────────────────────────────────────────────────

export default function MapView() {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();

  // ── Server data ────────────────────────────────────────────────────────────
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
  const { data: sensors = [], refetch: refetchSensors } = useQuery({
    queryKey: ['sensors', id],
    queryFn: () => api.sensors.list(id!),
    enabled: !!id,
  });
  const { data: geoFeatures = [], refetch: refetchGeoFeatures } = useQuery({
    queryKey: ['geo-features', id],
    queryFn: () => api.emergency.getFeatures(id!),
    enabled: !!id,
  });

  // ── Panel state ────────────────────────────────────────────────────────────
  const [simPanelOpen, setSimPanelOpen] = useState(false);
  const [controlCenterOpen, setControlCenterOpen] = useState(false);
  const [addEntityOpen, setAddEntityOpen] = useState(false);
  const [uploadLayerOpen, setUploadLayerOpen] = useState(false);

  const openPanel = (panel: 'sim' | 'control' | 'entity' | 'upload') => {
    setSimPanelOpen(panel === 'sim');
    setControlCenterOpen(panel === 'control');
    setAddEntityOpen(panel === 'entity');
    setUploadLayerOpen(panel === 'upload');
  };

  const anyPanelOpen = simPanelOpen || controlCenterOpen || addEntityOpen;

  // ── Entity placement ───────────────────────────────────────────────────────
  const [placementMode, setPlacementMode] = useState(false);
  const [pendingCoord, setPendingCoord] = useState<{ lat: number; lng: number } | null>(null);
  const [entityType, setEntityType] = useState<EntityType>('Sensor');
  const [sensorType, setSensorType] = useState<SensorType>('SIREN');

  // ── Layer navigation ───────────────────────────────────────────────────────
  const [selectedLayerIdx, setSelectedLayerIdx] = useState<number | null>(null);
  const [selectedFeature, setSelectedFeature] = useState<object | null>(null);

  // ── GeoJSON upload ─────────────────────────────────────────────────────────
  const [geoCategory, setGeoCategory] = useState<GeoCategory>('buildings');
  const { handleGeoUpload, uploadProgress, isUploading: geoUploading } = useGeoUpload(id ?? '');

  // ── Simulation state ───────────────────────────────────────────────────────
  // Two-step flow: stage sensor → user picks origin on map → run simulation.
  const [simSensor, setSimSensor] = useState<Sensor | null>(null);
  const [userEvacOrigin, setUserEvacOrigin] = useState<{ lat: number; lng: number } | null>(null);
  const [simResult, setSimResult] = useState<EmergencySimResult | null>(null);
  const [flyToCoord, setFlyToCoord] = useState<[number, number] | null>(null);

  // ── Streaming state ────────────────────────────────────────────────────────
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamPhase, setStreamPhase] = useState<StreamPhase>('idle');
  const [streamingText, setStreamingText] = useState('');
  const abortRef = useRef<AbortController | null>(null);

  // ── Mutations ──────────────────────────────────────────────────────────────
  const addSensorMutation = useMutation({
    mutationFn: api.sensors.create,
    onSuccess: () => {
      refetchSensors();
      setPendingCoord(null);
      setPlacementMode(false);
      toast.success('Sensor placed');
    },
    onError: () => toast.error('Failed to add sensor'),
  });

  const deleteSensorMutation = useMutation({
    mutationFn: api.sensors.delete,
    onSuccess: () => { refetchSensors(); toast.success('Sensor removed'); },
  });

  const addGeoFeatureMutation = useMutation({
    mutationFn: api.emergency.addFeature,
    onSuccess: () => {
      refetchGeoFeatures();
      setPendingCoord(null);
      setPlacementMode(false);
      toast.success('Feature placed');
    },
    onError: () => toast.error('Failed to add feature'),
  });

  const deleteGeoFeatureMutation = useMutation({
    mutationFn: api.emergency.deleteFeature,
    onSuccess: () => refetchGeoFeatures(),
  });

  // No simulateMutation — simulation now uses SSE streaming via handleRunSimulation.

  // True while the sim panel is open, a sensor is staged, and we haven't fired yet.
  // During this phase, map clicks set the evacuation origin instead of placing entities.
  const originPickingMode =
    simPanelOpen && simSensor !== null && !isStreaming && simResult === null;

  // Draw the evacuation route from the USER'S origin, never from the sensor.
  const evacuationRoute = useMemo(() => {
    const nf = simResult?.nearest_feature;
    if (!nf || !userEvacOrigin) return null;
    return {
      from: [userEvacOrigin.lat, userEvacOrigin.lng] as [number, number],
      to: [nf.lat, nf.lng] as [number, number],
    };
  }, [simResult, userEvacOrigin]);

  // ── Handlers ───────────────────────────────────────────────────────────────

  const handleMapClick = (lat: number, lng: number) => {
    if (originPickingMode) {
      // Origin-picking phase: capture user location, do not place an entity.
      setUserEvacOrigin({ lat, lng });
    } else if (placementMode) {
      setPendingCoord({ lat, lng });
    }
  };

  // Step 1 (from picker list inside SimulationOverlay): stage the sensor.
  // No simulation fired here — waits for the user to set their origin.
  const handleSelectSensor = (sensor: Sensor) => {
    setSimSensor(sensor);
    setSimResult(null);
    setUserEvacOrigin(null);
  };

  // Step 1 (from map popup or ControlCenterDrawer): stage sensor and open sim panel.
  const handleSimulateSensor = (sensor: Sensor) => {
    setSimSensor(sensor);
    setSimResult(null);
    setUserEvacOrigin(null);
    openPanel('sim');
  };

  // Step 3: called by "Run Simulation" button — only reachable when origin is set.
  // Consumes the SSE stream: updates streamPhase + streamingText on every event,
  // then resolves simResult when the final "result" event arrives.
  const handleRunSimulation = async () => {
    if (!simSensor || !userEvacOrigin || !id) return;

    abortRef.current = new AbortController();
    setIsStreaming(true);
    setStreamPhase('connecting');
    setStreamingText('');
    setSimResult(null);

    const decoder = new TextDecoder();
    let buffer = '';

    try {
      const reader = await api.emergency.simulateStream(
        {
          workspace_id: id,
          sensor_id: simSensor.sensor_id,
          origin_lat: userEvacOrigin.lat,
          origin_lng: userEvacOrigin.lng,
        },
        abortRef.current.signal,
      );

      // Drain the SSE stream until the server closes it.
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });

        // SSE events are separated by a blank line (\n\n).
        const events = buffer.split('\n\n');
        buffer = events.pop() ?? '';

        for (const block of events) {
          if (!block.trim()) continue;

          let eventName = 'message';
          let data = '';
          for (const line of block.split('\n')) {
            if (line.startsWith('event: ')) eventName = line.slice(7).trim();
            else if (line.startsWith('data: ')) data = line.slice(6);
          }

          // Skip blocks with no data payload — JSON.parse('') throws.
          if (!data.trim()) continue;

          try {
            if (eventName === 'status') {
              setStreamPhase(JSON.parse(data) as StreamPhase);
            } else if (eventName === 'token') {
              const chunk = JSON.parse(data) as string;
              setStreamingText(prev => prev + chunk);
            } else if (eventName === 'result') {
              const result = JSON.parse(data) as EmergencySimResult;
              setSimResult(result);
              setStreamPhase('done');
              toast.success('Simulation complete');
            } else if (eventName === 'error') {
              const err = JSON.parse(data) as { detail: string };
              throw new Error(err.detail);
            }
          } catch (parseErr) {
            // Re-throw intentional errors; swallow corrupt SSE frames.
            if ((parseErr as Error).message && !(parseErr instanceof SyntaxError)) throw parseErr;
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        toast.error('Simulation failed');
      }
    } finally {
      setIsStreaming(false);
    }
  };

  // Reset sensor selection back to the picker phase.
  const handleResetSensor = () => {
    abortRef.current?.abort();
    setSimSensor(null);
    setUserEvacOrigin(null);
    setSimResult(null);
    setStreamingText('');
    setStreamPhase('idle');
    setIsStreaming(false);
  };

  // Full clear: wipes all simulation state and closes the panel.
  const handleClearSimulation = () => {
    abortRef.current?.abort();
    setSimSensor(null);
    setUserEvacOrigin(null);
    setSimResult(null);
    setStreamingText('');
    setStreamPhase('idle');
    setIsStreaming(false);
    setSimPanelOpen(false);
  };

  const handlePlaceEntity = () => {
    if (!pendingCoord) return;
    const { lat, lng } = pendingCoord;
    if (entityType === 'Sensor') {
      addSensorMutation.mutate({ workspace_id: id!, sensor_type: sensorType, lat, lng });
    } else {
      addGeoFeatureMutation.mutate({
        workspace_id: id!,
        feature_type: ENTITY_TO_FEATURE[entityType],
        label: `${entityType} ${new Date().toLocaleTimeString('en', { hour: '2-digit', minute: '2-digit' })}`,
        lat,
        lng,
      });
    }
  };


  const handleFeatureClick = (_feature: Feature<Geometry, GeoJsonProperties>) => {};

  return (
    <div className="h-screen flex flex-col overflow-hidden">
      <Header workspaceName={workspace?.name} />

      <div className="flex-1 relative min-h-0 overflow-hidden">
        <div className="absolute inset-0">
          <MapComponent
            layers={layers}
            sensors={sensors}
            geoFeatures={geoFeatures}
            tagMode={placementMode}
            originPickingMode={originPickingMode}
            userEvacOrigin={userEvacOrigin}
            onMapClick={handleMapClick}
            onSensorDelete={sid => deleteSensorMutation.mutate(sid)}
            onGeoFeatureDelete={fid => deleteGeoFeatureMutation.mutate(fid)}
            onSensorSimulate={handleSimulateSensor}
            selectedLayerIndex={selectedLayerIdx}
            selectedFeature={selectedFeature}
            onFeatureClick={handleFeatureClick}
            flyToCoord={flyToCoord}
            evacuationRoute={evacuationRoute}
            className="h-full"
          />
        </div>

        {/* ── Back button ─────────────────────────────────────────────────── */}
        <div className="absolute top-4 left-4 z-[850]">
          <motion.button
            whileHover={{ x: -2 }}
            whileTap={{ scale: 0.95 }}
            transition={{ type: 'spring', stiffness: 400, damping: 20 }}
            onClick={() => navigate(`/workspace/${id}`)}
            className="flex items-center gap-1.5 px-3 py-2 rounded-xl bg-card/90 backdrop-blur-sm border border-border text-sm font-medium text-foreground hover:bg-card shadow-lg transition-colors"
          >
            <ArrowLeft className="h-4 w-4" />
            Back
          </motion.button>
        </div>

        {/* ── Top-center banners (only one shown at a time) ──────────────── */}
        <AnimatePresence>
          {originPickingMode && (
            <motion.div
              key="origin-banner"
              initial={{ opacity: 0, y: -16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              className="absolute top-4 left-1/2 -translate-x-1/2 z-[850] flex items-center gap-2 px-4 py-2.5 rounded-full text-sm font-semibold shadow-xl pointer-events-none select-none"
              style={{ background: '#2563eb', color: '#fff', boxShadow: '0 4px 20px rgba(37,99,235,0.45)' }}
            >
              <MapPin className="h-4 w-4 shrink-0" />
              {userEvacOrigin
                ? 'Origin set — click to change'
                : 'Click map to set your evacuation starting point'}
            </motion.div>
          )}

          {placementMode && !originPickingMode && (
            <motion.div
              key="placement-banner"
              initial={{ opacity: 0, y: -16 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -16 }}
              className="absolute top-4 left-1/2 -translate-x-1/2 z-[850] flex items-center gap-2 px-4 py-2.5 rounded-full bg-primary text-primary-foreground text-sm font-semibold shadow-xl"
              style={{ boxShadow: '0 4px 20px rgba(239,68,68,0.4)' }}
            >
              <Crosshair className="h-4 w-4 animate-spin" style={{ animationDuration: '3s' }} />
              Click map to place {entityType}
              <button
                onClick={() => { setPlacementMode(false); setPendingCoord(null); }}
                className="ml-1 hover:opacity-75 transition-opacity"
              >
                <X className="h-4 w-4" />
              </button>
            </motion.div>
          )}
        </AnimatePresence>

        {/* ── Floating action dock ────────────────────────────────────────── */}
        <motion.div
          className="absolute top-1/2 -translate-y-1/2 z-[850] flex flex-col gap-2"
          animate={{ right: anyPanelOpen ? 444 : 16 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
        >
          <DockButton
            icon={Zap}
            label="Sim"
            prominent
            pulse={isStreaming}
            onClick={() => {
              if (simPanelOpen) { setSimPanelOpen(false); } else openPanel('sim');
            }}
          />
          <DockButton
            icon={Plus}
            label="Entity"
            active={addEntityOpen}
            onClick={() => { if (addEntityOpen) setAddEntityOpen(false); else openPanel('entity'); }}
          />
          <DockButton
            icon={Upload}
            label="Layer"
            onClick={() => setUploadLayerOpen(true)}
          />
          <DockButton
            icon={Cpu}
            label="Control"
            active={controlCenterOpen}
            onClick={() => { if (controlCenterOpen) setControlCenterOpen(false); else openPanel('control'); }}
          />
        </motion.div>

        {/* ── Alarm widget — visible when sim panel is closed ─────────────── */}
        <AnimatePresence>
          {(simResult || isStreaming) && !simPanelOpen && (
            <AlarmWidget
              sensor={simSensor}
              result={simResult}
              isLoading={isStreaming}
              onClick={() => openPanel('sim')}
              onClear={handleClearSimulation}
            />
          )}
        </AnimatePresence>

        {/* ── Simulation overlay ──────────────────────────────────────────── */}
        <AnimatePresence>
          {simPanelOpen && (
            <SimulationOverlay
              sensors={sensors}
              simSensor={simSensor}
              simResult={simResult}
              isLoading={isStreaming}
              streamPhase={streamPhase}
              streamingText={streamingText}
              userEvacOrigin={userEvacOrigin}
              onSelectSensor={handleSelectSensor}
              onRunSimulation={handleRunSimulation}
              onResetSensor={handleResetSensor}
              onClearSimulation={handleClearSimulation}
              onClose={() => setSimPanelOpen(false)}
              onFlyToFeature={(lat, lng) => setFlyToCoord([lat, lng])}
            />
          )}
        </AnimatePresence>

        {/* ── Control center drawer ───────────────────────────────────────── */}
        <AnimatePresence>
          {controlCenterOpen && (
            <ControlCenterDrawer
              sensors={sensors}
              layers={layers}
              geoFeatures={geoFeatures}
              selectedLayerIdx={selectedLayerIdx}
              onSelectLayer={i => { setSelectedLayerIdx(i); setSelectedFeature(null); }}
              onDeleteSensor={sid => deleteSensorMutation.mutate(sid)}
              onSimulateSensor={handleSimulateSensor}
              onFlyToSensor={s => { if (s.lat != null && s.lng != null) setFlyToCoord([s.lat, s.lng]); }}
              onDeleteFeature={fid => deleteGeoFeatureMutation.mutate(fid)}
              onClose={() => setControlCenterOpen(false)}
            />
          )}
        </AnimatePresence>

        {/* ── Add entity panel ────────────────────────────────────────────── */}
        <AnimatePresence>
          {addEntityOpen && (
            <AddEntityPanel
              placementMode={placementMode}
              onTogglePlacement={() => setPlacementMode(p => !p)}
              pendingCoord={pendingCoord}
              onClearCoord={() => setPendingCoord(null)}
              onCoordChange={coord => setPendingCoord(coord)}
              entityType={entityType}
              onEntityTypeChange={setEntityType}
              sensorType={sensorType}
              onSensorTypeChange={setSensorType}
              onPlace={handlePlaceEntity}
              isPlacing={addSensorMutation.isPending || addGeoFeatureMutation.isPending}
              onClose={() => { setAddEntityOpen(false); setPlacementMode(false); setPendingCoord(null); }}
            />
          )}
        </AnimatePresence>
      </div>

      <UploadLayerModal
        open={uploadLayerOpen}
        onClose={() => setUploadLayerOpen(false)}
        geoCategory={geoCategory}
        onGeoCategoryChange={setGeoCategory}
        onUpload={file => handleGeoUpload(file, geoCategory)}
        isUploading={geoUploading}
        uploadProgress={uploadProgress}
      />
    </div>
  );
}
