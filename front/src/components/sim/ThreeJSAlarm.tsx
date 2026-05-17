/**
 * ThreeJSAlarm — WebGL pulsing rings rendered with Three.js.
 * Shows urgency-colored concentric torus rings expanding from a glowing center disk.
 */
import { useEffect, useRef } from 'react';
import * as THREE from 'three';

type Urgency = 'low' | 'medium' | 'high' | 'critical';

interface ThreeJSAlarmProps {
  active: boolean;
  urgency?: Urgency;
  size?: number;
}

const URGENCY_COLOR: Record<Urgency, number> = {
  critical: 0xef4444,
  high:     0xf97316,
  medium:   0xeab308,
  low:      0x22c55e,
};

export function ThreeJSAlarm({ active, urgency = 'high', size = 160 }: ThreeJSAlarmProps) {
  const mountRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!mountRef.current || !active) return;
    const mount = mountRef.current;
    const color = URGENCY_COLOR[urgency];

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(size, size);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    mount.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(55, 1, 0.1, 50);
    camera.position.z = 4;

    // Four pulsing rings with staggered phase
    const rings: { mesh: THREE.Mesh; offset: number }[] = [];
    for (let i = 0; i < 4; i++) {
      const geo = new THREE.TorusGeometry(0.38, 0.032, 8, 52);
      const mat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0 });
      const mesh = new THREE.Mesh(geo, mat);
      mesh.rotation.x = 0.28;
      scene.add(mesh);
      rings.push({ mesh, offset: i * 0.26 });
    }

    // Central glowing disk
    const centerMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.85 });
    const center = new THREE.Mesh(new THREE.CircleGeometry(0.2, 40), centerMat);
    scene.add(center);

    // Outer halo
    const haloMat = new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.25 });
    const halo = new THREE.Mesh(new THREE.CircleGeometry(0.38, 40), haloMat);
    scene.add(halo);

    let frameId: number;
    const clock = new THREE.Clock();

    const animate = () => {
      frameId = requestAnimationFrame(animate);
      const t = clock.getElapsedTime();

      rings.forEach(({ mesh, offset }) => {
        const phase = (t * 0.65 + offset) % 1;
        mesh.scale.setScalar(0.55 + phase * 2.8);
        (mesh.material as THREE.MeshBasicMaterial).opacity = Math.pow(1 - phase, 1.4) * 0.85;
        mesh.rotation.z = t * 0.18;
      });

      centerMat.opacity = 0.6 + 0.4 * Math.sin(t * 4.2);
      center.rotation.z = t * 0.9;
      haloMat.opacity = 0.15 + 0.15 * Math.sin(t * 2.1);

      renderer.render(scene, camera);
    };

    animate();

    return () => {
      cancelAnimationFrame(frameId);
      renderer.dispose();
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
    };
  }, [active, urgency, size]);

  if (!active) return null;

  return (
    <div
      ref={mountRef}
      style={{ width: size, height: size }}
      className="pointer-events-none"
    />
  );
}
