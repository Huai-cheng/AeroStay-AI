"use client";

import { Canvas, useFrame } from "@react-three/fiber";
import { Float, Line, Sparkles } from "@react-three/drei";
import { Suspense, useMemo, useRef } from "react";
import * as THREE from "three";

function Aircraft({ intensity }: { intensity: number }) {
  const group = useRef<THREE.Group>(null);
  const curve = useMemo(
    () => new THREE.CatmullRomCurve3([
      new THREE.Vector3(-4.8, 1.4, 0),
      new THREE.Vector3(-2.2, 3.25, -0.2),
      new THREE.Vector3(0.5, 2.35, 0),
      new THREE.Vector3(3.15, 0.9, 0.2),
    ]),
    [],
  );
  const points = useMemo(() => curve.getPoints(80), [curve]);

  useFrame(({ clock }) => {
    if (!group.current) return;
    const t = (clock.getElapsedTime() * (0.055 + intensity * 0.018)) % 1;
    const point = curve.getPointAt(t);
    const tangent = curve.getTangentAt(Math.min(t + 0.002, 1));
    group.current.position.copy(point);
    group.current.rotation.z = Math.atan2(tangent.y, tangent.x);
  });

  return (
    <>
      <Line points={points} color="#35e8d0" lineWidth={1.25} transparent opacity={0.55} />
      <group ref={group} scale={0.22}>
        <mesh rotation={[0, 0, -Math.PI / 2]}>
          <cylinderGeometry args={[0.28, 0.38, 3.2, 16]} />
          <meshStandardMaterial color="#f7fbff" metalness={0.5} roughness={0.25} />
        </mesh>
        <mesh position={[1.82, 0, 0]} rotation={[0, 0, -Math.PI / 2]}>
          <coneGeometry args={[0.28, 0.72, 16]} />
          <meshStandardMaterial color="#dff8ff" metalness={0.48} roughness={0.2} />
        </mesh>
        <mesh position={[-0.1, 0, 0]}>
          <boxGeometry args={[1.15, 0.10, 3.25]} />
          <meshStandardMaterial color="#4de4d1" metalness={0.35} />
        </mesh>
        <mesh position={[-1.2, 0.05, 0]}>
          <boxGeometry args={[0.66, 0.09, 1.42]} />
          <meshStandardMaterial color="#a4b8d1" />
        </mesh>
        <mesh position={[-1.35, 0.35, 0]} rotation={[Math.PI / 2, 0, 0]}>
          <boxGeometry args={[0.55, 0.08, 0.72]} />
          <meshStandardMaterial color="#38e0ca" />
        </mesh>
      </group>
    </>
  );
}

function PassengerFlow({ intensity }: { intensity: number }) {
  const points = useRef<Array<THREE.Mesh | null>>([]);
  const count = 22;
  useFrame(({ clock }) => {
    points.current.forEach((mesh, index) => {
      if (!mesh) return;
      const progress = (clock.getElapsedTime() * (0.10 + intensity * 0.025) + index / count) % 1;
      const diverted = index % 6 === 0 && progress > 0.46;
      mesh.position.x = -1.45 + progress * 4.75;
      mesh.position.y = -0.64 + Math.sin(progress * Math.PI) * 0.22 - (diverted ? (progress - 0.46) * 2.2 : 0);
      mesh.position.z = ((index % 4) - 1.5) * 0.10;
      const scale = diverted ? Math.max(0.22, 1 - (progress - 0.46) * 1.7) : 1;
      mesh.scale.setScalar(scale);
    });
  });
  return (
    <group>
      {Array.from({ length: count }).map((_, index) => (
        <mesh key={index} ref={(node) => { points.current[index] = node; }}>
          <sphereGeometry args={[0.045 + (index % 3) * 0.008, 8, 8]} />
          <meshStandardMaterial
            color={index % 6 === 0 ? "#70869d" : "#49e4cf"}
            emissive={index % 6 === 0 ? "#405267" : "#2fc9b5"}
            emissiveIntensity={0.85}
          />
        </mesh>
      ))}
    </group>
  );
}

function HotelCluster({ glow }: { glow: number }) {
  const heights = [1.1, 1.7, 2.5, 1.45, 2.05, 1.25, 1.8];
  return (
    <group position={[3.75, -1.55, 0]}>
      {heights.map((height, index) => (
        <mesh key={height + index} position={[(index - 3) * 0.46, height / 2, (index % 2) * 0.3]}>
          <boxGeometry args={[0.34, height, 0.48]} />
          <meshStandardMaterial
            color={index % 2 ? "#173c54" : "#1d5261"}
            emissive="#f4b860"
            emissiveIntensity={0.05 + glow * (0.25 + index * 0.025)}
            roughness={0.62}
          />
        </mesh>
      ))}
      <pointLight position={[0, 2.1, 1]} color="#f4b860" intensity={1.8 * glow} distance={6} />
    </group>
  );
}

function Scene({ demandLift }: { demandLift: number }) {
  const intensity = Math.min(1, Math.max(0.1, Math.abs(demandLift) / 100000));
  return (
    <>
      <ambientLight intensity={0.8} />
      <directionalLight position={[-3, 5, 4]} intensity={2.4} color="#d9f8ff" />
      <pointLight position={[-3, 2, 2]} color="#6c63ff" intensity={5} distance={7} />
      <fog attach="fog" args={["#071221", 7, 15]} />
      <Aircraft intensity={intensity} />
      <PassengerFlow intensity={intensity} />
      <HotelCluster glow={0.35 + intensity} />
      <Sparkles count={36} scale={[10, 5, 2]} size={1.4} speed={0.25} color="#55ead6" opacity={0.45} />
      <Float speed={1.3} rotationIntensity={0.08} floatIntensity={0.12}>
        <mesh position={[0, -1.72, -0.25]} rotation={[-Math.PI / 2, 0, 0]}>
          <planeGeometry args={[12, 5]} />
          <meshStandardMaterial color="#081a2b" roughness={0.92} />
        </mesh>
      </Float>
    </>
  );
}

export function JourneyScene({ demandLift = 0 }: { demandLift?: number }) {
  return (
    <div className="journey-canvas" aria-label="Animated flight path arriving at Abu Dhabi hotels">
      <Canvas camera={{ position: [0, 1.1, 8.2], fov: 46 }} dpr={[1, 1.5]} gl={{ antialias: true, alpha: true }}>
        <Suspense fallback={null}>
          <Scene demandLift={demandLift} />
        </Suspense>
      </Canvas>
      <div className="scene-caption">
        <span>Origin capacity</span><i /><span>Passenger conversion</span><i /><span>Hotel demand</span>
      </div>
    </div>
  );
}
