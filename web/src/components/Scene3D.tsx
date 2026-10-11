// The hero view. 1 scene unit = 100 mm, y up.
//
// The true lander sits at its real height; the ground under it is a block that rises or drops
// with the terrain (the rig's slide-in plateau), so "the ground fell away" is something you see.
// Each brain's belief is a ghost lander drawn at ground + its estimate: a ghost below the true
// lander means that brain thinks it is lower than it really is.
import { Edges, Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Component, useEffect, useMemo, useRef, type ReactNode } from "react";
import * as THREE from "three";
import { C, ERR_BAD_MM, mm, signed, unit } from "../theme";
import type { State } from "../types";

const U = 0.01; // scene units per mm
const PAD = 3; // side of the terrain block under the lander
const TILE = 8; // the moon texture repeats every TILE units
const DEPTH = 1.4; // how far the terrain block extends below its top
// Simulator camera: 320x240 px at f = 260 px. A webcam on the rig is close enough for the drawing.
const FOV_W = 160 / 260;
const FOV_D = 120 / 260;
const RULER: [number, number] = [-1.25, 1.25];

function moonTexture(): THREE.CanvasTexture {
  const n = 1024;
  const cv = document.createElement("canvas");
  cv.width = cv.height = n;
  const g = cv.getContext("2d")!;
  let seed = 7;
  const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
  // draw at every wrap offset so the texture tiles without seams
  const wrapped = (x: number, y: number, r: number, draw: (x: number, y: number) => void) => {
    for (const dx of [-n, 0, n])
      for (const dy of [-n, 0, n])
        if (x + dx > -r && x + dx < n + r && y + dy > -r && y + dy < n + r) draw(x + dx, y + dy);
  };
  g.fillStyle = "#77777b";
  g.fillRect(0, 0, n, n);
  for (let i = 0; i < 2600; i++) {
    const r = 4 + rnd() * 46;
    const fill = rnd() < 0.5 ? `rgba(0,0,0,${0.02 + rnd() * 0.05})` : `rgba(255,255,255,${0.015 + rnd() * 0.04})`;
    wrapped(rnd() * n, rnd() * n, r, (x, y) => {
      g.fillStyle = fill;
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.fill();
    });
  }
  for (let i = 0; i < 150; i++) {
    const r = 3 + rnd() * rnd() * 44;
    wrapped(rnd() * n, rnd() * n, r, (x, y) => {
      const bowl = g.createRadialGradient(x, y, 0, x, y, r);
      bowl.addColorStop(0, "rgba(0,0,0,0.34)");
      bowl.addColorStop(0.72, "rgba(0,0,0,0.16)");
      bowl.addColorStop(0.9, "rgba(255,255,255,0.2)");
      bowl.addColorStop(1, "rgba(255,255,255,0)");
      g.fillStyle = bowl;
      g.beginPath();
      g.arc(x, y, r, 0, Math.PI * 2);
      g.fill();
    });
  }
  const tex = new THREE.CanvasTexture(cv);
  tex.colorSpace = THREE.SRGBColorSpace;
  tex.wrapS = tex.wrapT = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  return tex;
}

function useTerrain() {
  return useMemo(() => {
    const surfaceTex = moonTexture();
    surfaceTex.repeat.set(1 / TILE, 1 / TILE);
    // same image on the block top, offset so it lines up with the surface when flush
    const padTex = surfaceTex.clone();
    padTex.repeat.set(PAD / TILE, PAD / TILE);
    padTex.offset.set(-PAD / 2 / TILE, -PAD / 2 / TILE);
    padTex.needsUpdate = true;


    const h = PAD / 2;
    const shape = new THREE.Shape();
    shape.moveTo(-20, -20);
    shape.lineTo(20, -20);
    shape.lineTo(20, 20);
    shape.lineTo(-20, 20);
    shape.closePath();
    const hole = new THREE.Path();
    hole.moveTo(-h, -h);
    hole.lineTo(-h, h);
    hole.lineTo(h, h);
    hole.lineTo(h, -h);
    hole.closePath();
    shape.holes.push(hole);

    const rim = new THREE.BufferGeometry().setFromPoints(
      [[-h, -h], [h, -h], [h, -h], [h, h], [h, h], [-h, h], [-h, h], [-h, -h]].map(
        ([x, z]) => new THREE.Vector3(x, 0, z),
      ),
    );
    return { surfaceTex, padTex, surface: new THREE.ShapeGeometry(shape), rim };
  }, []);
}

const UP = new THREE.Vector3(0, 1, 0);
const LEGS = [0, 1, 2, 3].map((i) => {
  const a = Math.PI / 4 + (i * Math.PI) / 2;
  const top = new THREE.Vector3(0.26 * Math.cos(a), 0.08, 0.26 * Math.sin(a));
  const foot = new THREE.Vector3(0.5 * Math.cos(a), -0.27, 0.5 * Math.sin(a));
  const d = foot.clone().sub(top);
  return {
    foot,
    mid: top.clone().add(foot).multiplyScalar(0.5),
    len: d.length(),
    quat: new THREE.Quaternion().setFromUnitVectors(UP, d.clone().normalize()),
  };
});

/** Origin is the sensor plane (underside of the body), which is what "altitude" refers to. */
function Lander({ ghost }: { ghost?: string }) {
  const skin = ghost ? (
    <meshBasicMaterial color={ghost} transparent opacity={0.07} depthWrite={false} />
  ) : (
    <meshStandardMaterial color={C.truth} metalness={0.35} roughness={0.5} flatShading />
  );
  const strut = ghost ? (
    <meshBasicMaterial color={ghost} transparent opacity={0.55} depthWrite={false} />
  ) : (
    <meshStandardMaterial color="#aab2bd" metalness={0.6} roughness={0.4} />
  );
  const edges = ghost ? <Edges threshold={20} color={ghost} /> : null;
  return (
    <group>
      <mesh castShadow={!ghost} position={[0, 0.13, 0]}>
        <cylinderGeometry args={[0.25, 0.3, 0.26, 8]} />
        {skin}
        {edges}
      </mesh>
      <mesh castShadow={!ghost} position={[0, 0.31, 0]}>
        <cylinderGeometry args={[0.15, 0.24, 0.1, 8]} />
        {skin}
        {edges}
      </mesh>
      <mesh position={[0, -0.06, 0]}>
        <cylinderGeometry args={[0.05, 0.11, 0.12, 12, 1, true]} />
        {ghost ? strut : <meshStandardMaterial color="#3a4048" metalness={0.7} roughness={0.5} side={THREE.DoubleSide} />}
      </mesh>
      {LEGS.map((l, i) => (
        <group key={i}>
          <mesh castShadow={!ghost} position={l.mid} quaternion={l.quat}>
            <cylinderGeometry args={[0.014, 0.014, l.len, 6]} />
            {strut}
          </mesh>
          <mesh castShadow={!ghost} position={l.foot}>
            <cylinderGeometry args={[0.07, 0.07, 0.02, 12]} />
            {skin}
            {edges}
          </mesh>
        </group>
      ))}
    </group>
  );
}

function useShapes() {
  return useMemo(() => {
    const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(
      ([x, z]) => new THREE.Vector3(x * FOV_W, -1, z * FOV_D),
    );
    const apex = new THREE.Vector3();
    const segs: THREE.Vector3[] = [];
    corners.forEach((c, i) => segs.push(apex, c, c, corners[(i + 1) % 4]));
    const frustumLines = new THREE.BufferGeometry().setFromPoints(segs);
    new THREE.LineSegments(frustumLines).computeLineDistances();
    const frustumFaces = new THREE.BufferGeometry().setFromPoints([apex, ...corners]);
    frustumFaces.setIndex([0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 1]);

    const beam = new THREE.CylinderGeometry(1, 1, 1, 10, 1, true).translate(0, -0.5, 0);
    const beamDash = new THREE.BufferGeometry().setFromPoints([apex, new THREE.Vector3(0, -1, 0)]);
    new THREE.LineSegments(beamDash).computeLineDistances();

    const ticks: THREE.Vector3[] = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 4.6, 0)];
    for (let y = 0; y <= 4.5; y += 0.5) {
      const w = y % 1 === 0 ? 0.2 : 0.1;
      ticks.push(new THREE.Vector3(-w, y, 0), new THREE.Vector3(w, y, 0));
    }
    const ruler = new THREE.BufferGeometry().setFromPoints(ticks);

    const stars = new Float32Array(700 * 3);
    let seed = 3;
    const rnd = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
    for (let i = 0; i < 700; i++) {
      const a = rnd() * Math.PI * 2;
      const y = 0.04 + rnd() * 0.96;
      const r = Math.sqrt(1 - y * y);
      stars.set([70 * r * Math.cos(a), 70 * y, 70 * r * Math.sin(a)], i * 3);
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.BufferAttribute(stars, 3));
    return { frustumLines, frustumFaces, beam, beamDash, ruler, starGeo };
  }, []);
}

type Smooth = { y: number; g: number; legacy: number; so: number; sigma: number; rf: number; nav: number; rfw: number; cam: number };

function Tag({ className, children }: { className: string; children: ReactNode }) {
  return (
    <Html zIndexRange={[4, 0]} style={{ pointerEvents: "none" }}>
      <div className={`tag ${className}`}>{children}</div>
    </Html>
  );
}

function Rig({ s }: { s: State }) {
  const terrain = useTerrain();

  // Real ground: during a mission replay, the orbiter image of where that lander actually came
  // down; otherwise a square of the LRO global mosaic. Neither is seamless, so they are mirrored
  // at the tile edges. If the file is missing the generated surface stays.
  const site = s.scenario?.site ? `/sites/${s.scenario.site.split("/").pop()}` : "/textures/lro_moon.jpg";
  useEffect(() => {
    const img = new Image();
    img.onload = () => {
      for (const t of [terrain.surfaceTex, terrain.padTex]) {
        t.image = img;
        t.wrapS = t.wrapT = THREE.MirroredRepeatWrapping;
        t.needsUpdate = true;
      }
    };
    img.src = site;
    return () => {
      img.onload = null;
    };
  }, [site, terrain]);

  const shapes = useShapes();
  const live = useRef(s);
  live.current = s;
  const sm = useRef<Smooth | null>(null);

  const lander = useRef<THREE.Group>(null!);
  const block = useRef<THREE.Group>(null!);
  const legacy = useRef<THREE.Group>(null!);
  const so = useRef<THREE.Group>(null!);
  const band = useRef<THREE.Mesh>(null!);
  const beam = useRef<THREE.Group>(null!);
  const beamLen = useRef<THREE.Group>(null!);
  const beamEnd = useRef<THREE.Group>(null!);
  const frustum = useRef<THREE.Group>(null!);
  const ruler = useRef<THREE.Group>(null!);
  const pipNav = useRef<THREE.Group>(null!);
  const pipRf = useRef<THREE.Group>(null!);
  const pipCam = useRef<THREE.Group>(null!);

  useFrame((_, dt) => {
    const s = live.current;
    const truth = s.truth ?? s.nav;
    const w = s.so.witness;
    const target: Smooth = {
      y: s.nav_raw * U, // height above the ground as it was at reset
      g: (s.nav_raw - truth) * U, // where the ground under the lander is now
      legacy: (s.legacy.est ?? truth) * U,
      so: (s.so.est ?? truth) * U,
      sigma: Math.max(s.so.sigma ?? 0, 2) * U,
      rf: (s.rf ?? truth) * U,
      nav: (w.nav?.h ?? s.nav) * U,
      rfw: (w.rf?.h ?? s.rf ?? truth) * U,
      cam: (w.cam?.h ?? s.cam ?? truth) * U,
    };
    const c = (sm.current ??= { ...target });
    const k = 1 - Math.exp(-Math.min(dt, 0.1) * 12);
    (Object.keys(target) as (keyof Smooth)[]).forEach((key) => (c[key] += (target[key] - c[key]) * k));

    lander.current.position.y = c.y;
    block.current.position.y = c.g;
    legacy.current.position.y = c.g + c.legacy;
    so.current.position.y = c.g + c.so;
    band.current.position.y = c.g + c.so;
    band.current.scale.y = c.sigma * 2;
    beam.current.position.y = c.y;
    beamLen.current.scale.y = c.rf;
    beamEnd.current.position.y = -c.rf;
    frustum.current.position.y = c.y;
    frustum.current.scale.setScalar(Math.max(c.y - c.g, 0.05));
    ruler.current.position.y = c.g;
    pipNav.current.position.y = c.nav;
    pipRf.current.position.y = c.rfw;
    pipCam.current.position.y = c.cam;
  });

  const truth = s.truth ?? s.nav;
  const rfOut = s.so.excluded.includes("rf");
  const camOut = s.so.excluded.includes("cam");
  const camOff = camOut || s.so.cam_abstain;
  const rfColor = rfOut ? C.off : C.rf;
  const camColor = camOff ? C.off : C.cam;
  const err = (est: number | null) => (est == null || s.truth == null ? null : est - s.truth);
  const tone = (e: number | null) => (e != null && Math.abs(e) > ERR_BAD_MM ? "bad" : "");

  return (
    <>
      {/* lunar surface with a cut-out for the terrain block */}
      <mesh geometry={terrain.surface} rotation-x={-Math.PI / 2} receiveShadow>
        <meshStandardMaterial map={terrain.surfaceTex} bumpMap={terrain.surfaceTex} bumpScale={1.2} roughness={1} />
      </mesh>
      <mesh position={[0, -DEPTH / 2, 0]}>
        <boxGeometry args={[PAD, DEPTH, PAD]} />
        <meshStandardMaterial color="#2b2d31" roughness={1} side={THREE.BackSide} />
      </mesh>
      <group ref={block}>
        <mesh rotation-x={-Math.PI / 2} position={[0, 0.002, 0]} receiveShadow>
          <planeGeometry args={[PAD, PAD]} />
          <meshStandardMaterial map={terrain.padTex} bumpMap={terrain.padTex} bumpScale={1.2} roughness={1} />
        </mesh>
        <mesh position={[0, -DEPTH / 2, 0]}>
          <boxGeometry args={[PAD - 0.01, DEPTH, PAD - 0.01]} />
          <meshStandardMaterial color="#4a4c51" roughness={1} />
        </mesh>
        <lineSegments geometry={terrain.rim} position={[0, 0.006, 0]}>
          <lineBasicMaterial color={C.ink} transparent opacity={0.22} />
        </lineSegments>
      </group>

      {/* altitude ruler standing on the ground, with one pip per witness */}
      <group ref={ruler} position={[RULER[0], 0, RULER[1]]}>
        <lineSegments geometry={shapes.ruler}>
          <lineBasicMaterial color={C.dim} transparent opacity={0.7} />
        </lineSegments>
        {[1, 2, 3, 4].map((y) => (
          <group key={y} position={[0, y, 0]}>
            <Tag className="tag-tick">{y * 100}</Tag>
          </group>
        ))}
        <group ref={pipNav}>
          <mesh>
            <octahedronGeometry args={[0.075]} />
            <meshBasicMaterial color={C.nav} />
          </mesh>
          <Tag className="tag-pip pip-nav">NAV</Tag>
        </group>
        <group ref={pipRf} visible={!!s.so.witness.rf}>
          <mesh>
            <octahedronGeometry args={[0.075]} />
            <meshBasicMaterial color={rfColor} />
          </mesh>
          {s.so.witness.rf && <Tag className={`tag-pip pip-rf ${rfOut ? "off" : ""}`}>RF</Tag>}
        </group>
        <group ref={pipCam} visible={!!s.so.witness.cam}>
          <mesh>
            <octahedronGeometry args={[0.075]} />
            <meshBasicMaterial color={camColor} />
          </mesh>
          {s.so.witness.cam && <Tag className={`tag-pip pip-cam ${camOut ? "off" : ""}`}>CAM</Tag>}
        </group>
      </group>

      {/* true lander */}
      <group ref={lander}>
        <Lander />
        <Tag className="tag-lander tag-truth">TRUE {mm(truth)} {unit()}</Tag>
      </group>

      {/* rangefinder beam: its length is the reading, so a wrong reading ends above or below the ground */}
      <group ref={beam} position={[0.13, 0, 0]} visible={s.rf != null}>
        <group ref={beamLen}>
          <mesh geometry={shapes.beam} scale={[0.012, 1, 0.012]} visible={!rfOut}>
            <meshBasicMaterial color={C.rf} />
          </mesh>
          <mesh geometry={shapes.beam} scale={[0.045, 1, 0.045]} visible={!rfOut}>
            <meshBasicMaterial color={C.rf} transparent opacity={0.16} depthWrite={false} blending={THREE.AdditiveBlending} />
          </mesh>
          {/* outvoted: dashed, and drawn through the ground so you can see where it thinks the surface is */}
          <lineSegments geometry={shapes.beamDash} visible={rfOut} renderOrder={9}>
            <lineDashedMaterial color={C.rf} dashSize={0.03} gapSize={0.03} depthTest={false} transparent opacity={0.8} />
          </lineSegments>
        </group>
        <group ref={beamEnd}>
          <mesh rotation-x={-Math.PI / 2} renderOrder={10}>
            <ringGeometry args={[0.07, 0.11, 24]} />
            <meshBasicMaterial color={C.rf} side={THREE.DoubleSide} depthTest={false} transparent />
          </mesh>
        </group>
      </group>

      {/* camera frustum: cyan while the camera is a witness, grey when abstaining, dashed when outvoted */}
      <group ref={frustum}>
        <lineSegments geometry={shapes.frustumLines} visible={!camOut}>
          <lineBasicMaterial color={camColor} transparent opacity={camOff ? 0.6 : 0.9} />
        </lineSegments>
        <lineSegments geometry={shapes.frustumLines} visible={camOut}>
          <lineDashedMaterial color={C.dim} dashSize={0.04} gapSize={0.035} />
        </lineSegments>
        <mesh geometry={shapes.frustumFaces}>
          <meshBasicMaterial color={camColor} transparent opacity={camOff ? 0.025 : 0.07} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      </group>

      {/* what each brain believes */}
      <group ref={legacy} scale={1.16}>
        <Lander ghost={C.legacy} />
        <Tag className={`tag-lander tag-legacy ${tone(err(s.legacy.est))}`}>LEGACY {signed(err(s.legacy.est))} {unit()}</Tag>
      </group>
      <group ref={so} scale={1.08}>
        <Lander ghost={C.so} />
        <Tag className={`tag-lander tag-so ${tone(err(s.so.est))}`}>SUBSIDIUM {signed(err(s.so.est))} {unit()}</Tag>
      </group>
      <mesh ref={band}>
        <cylinderGeometry args={[0.78, 0.78, 1, 40, 1, true]} />
        <meshBasicMaterial color={C.so} transparent opacity={0.2} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>

      <points geometry={shapes.starGeo}>
        <pointsMaterial color="#cfd6e4" size={0.3} transparent opacity={0.8} fog={false} />
      </points>
    </>
  );
}

class Boundary extends Component<{ fallback: ReactNode; children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export default function Scene3D({ s }: { s: State }) {
  return (
    <Boundary fallback={<div className="scene-fallback">3D view unavailable (no WebGL)</div>}>
      <Canvas shadows dpr={[1, 1.75]} camera={{ position: [6.1, 4.1, 7.5], fov: 38, near: 0.1, far: 200 }}>
        <color attach="background" args={[C.bg]} />
        <fog attach="fog" args={[C.bg, 14, 34]} />
        <ambientLight intensity={0.35} />
        <directionalLight
          position={[-7, 6, 4]}
          intensity={2.6}
          castShadow
          shadow-mapSize={[1024, 1024]}
          shadow-camera-left={-6}
          shadow-camera-right={6}
          shadow-camera-top={6}
          shadow-camera-bottom={-6}
          shadow-camera-far={30}
        />
        <Rig s={s} />
        <OrbitControls
          target={[0, 2.3, 0]}
          autoRotate
          autoRotateSpeed={0.45}
          enablePan={false}
          enableDamping
          minDistance={5}
          maxDistance={16}
          maxPolarAngle={Math.PI / 2 - 0.06}
        />
      </Canvas>
    </Boundary>
  );
}
