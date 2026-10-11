// The 3D view. One scene unit is 100 mm and y points up.
//
// The ground never moves. The true lander sits at its real height above it, so when the terrain
// changes (the rig's plateau slides out) the lander's true height jumps up. Each brain's belief is
// a ghost lander drawn at its own estimate, so a ghost below the true lander means that brain
// thinks it's lower than it really is.
import { Edges, Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";
import { C, ERR_BAD_MM, mm, signed, unit } from "../theme";
import type { State } from "../types";

const U = 0.01; // scene units per mm
const GROUND = 40; // side length of the ground square
const TILE = 8; // the ground texture repeats every TILE units
// The simulated camera is 320x240 px with a focal length of 260 px, and a webcam is close enough.
const FOV_W = 160 / 260;
const FOV_D = 120 / 260;

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

/** A lander whose origin is the sensor plane (the underside of the body), which is what "altitude" means. A ghost is see-through. */
function Lander({ ghost }: { ghost?: string }) {
  const skin = ghost
    ? <meshBasicMaterial color={ghost} transparent opacity={0.07} depthWrite={false} />
    : <meshStandardMaterial color={C.truth} metalness={0.35} roughness={0.5} flatShading />;
  const strut = ghost
    ? <meshBasicMaterial color={ghost} transparent opacity={0.55} depthWrite={false} />
    : <meshStandardMaterial color="#aab2bd" metalness={0.6} roughness={0.4} />;
  const outline = ghost ? <Edges threshold={20} color={ghost} /> : null;
  return (
    <group>
      <mesh position={[0, 0.13, 0]} castShadow={!ghost}>
        <cylinderGeometry args={[0.25, 0.3, 0.26, 8]} />
        {skin}
        {outline}
      </mesh>
      <mesh position={[0, 0.31, 0]} castShadow={!ghost}>
        <cylinderGeometry args={[0.15, 0.24, 0.1, 8]} />
        {skin}
        {outline}
      </mesh>
      {LEGS.map((l, i) => (
        <group key={i}>
          <mesh position={l.mid} quaternion={l.quat} castShadow={!ghost}>
            <cylinderGeometry args={[0.014, 0.014, l.len, 6]} />
            {strut}
          </mesh>
          <mesh position={l.foot} castShadow={!ghost}>
            <cylinderGeometry args={[0.07, 0.07, 0.02, 12]} />
            {skin}
            {outline}
          </mesh>
        </group>
      ))}
    </group>
  );
}

/** Geometry that never changes, built once. */
function useShapes() {
  return useMemo(() => {
    // the camera's view: a pyramid from the lander down to the ground, one unit tall
    const apex = new THREE.Vector3();
    const corners = [[-1, -1], [1, -1], [1, 1], [-1, 1]].map(([x, z]) => new THREE.Vector3(x * FOV_W, -1, z * FOV_D));
    const edges = corners.flatMap((c, i) => [apex, c, c, corners[(i + 1) % 4]]);
    const frustumLines = new THREE.BufferGeometry().setFromPoints(edges);
    const frustumFaces = new THREE.BufferGeometry().setFromPoints([apex, ...corners]);
    frustumFaces.setIndex([0, 1, 2, 0, 2, 3, 0, 3, 4, 0, 4, 1]);

    // the rangefinder beam as a thin tube, plus a dashed line for when it's outvoted
    const beam = new THREE.CylinderGeometry(1, 1, 1, 10, 1, true).translate(0, -0.5, 0);
    const beamDash = new THREE.BufferGeometry().setFromPoints([apex, new THREE.Vector3(0, -1, 0)]);
    new THREE.LineSegments(beamDash).computeLineDistances();

    // a ruler 4.5 units tall (450 mm) with a tick every 50 mm
    const ticks = [new THREE.Vector3(0, 0, 0), new THREE.Vector3(0, 4.6, 0)];
    for (let y = 0; y <= 4.5; y += 0.5) ticks.push(new THREE.Vector3(y % 1 ? -0.1 : -0.2, y, 0), new THREE.Vector3(y % 1 ? 0.1 : 0.2, y, 0));

    // a thin sky of stars on a big sphere (the Moon has no atmosphere to hide them)
    const stars = new Float32Array(900 * 3);
    for (let i = 0; i < 900; i++) {
      const a = Math.random() * Math.PI * 2;
      const y = 0.05 + Math.random() * 0.95;
      const r = Math.sqrt(1 - y * y);
      stars.set([70 * r * Math.cos(a), 70 * y, 70 * r * Math.sin(a)], i * 3);
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.BufferAttribute(stars, 3));
    return { frustumLines, frustumFaces, beam, beamDash, starGeo, ruler: new THREE.BufferGeometry().setFromPoints(ticks) };
  }, []);
}

/**
 * The ground texture, repeating every TILE units. During a mission replay it's the real orbiter
 * photo of the crash site. Photos don't tile, so they're mirrored at the edges.
 */
function useGround(url: string) {
  const [tex, setTex] = useState<THREE.Texture | null>(null);
  useEffect(() => {
    new THREE.TextureLoader().load(url, (t) => {
      t.colorSpace = THREE.SRGBColorSpace;
      t.wrapS = t.wrapT = THREE.MirroredRepeatWrapping;
      t.repeat.set(GROUND / TILE, GROUND / TILE);
      setTex(t);
    });
  }, [url]);
  return tex;
}

/**
 * The camera's hazard grid as a small texture: one coloured square per tile, green where the tile is
 * about the same height as the ground and red where it differs by 8% of the altitude or more, with
 * the safest tile outlined. It's laid on the ground inside the camera's footprint.
 */
function useHazardTexture(hazard: number[][] | null, site: [number, number] | null) {
  const canvas = useMemo(() => {
    const c = document.createElement("canvas");
    c.width = c.height = 192;
    return c;
  }, []);
  const texture = useMemo(() => {
    const t = new THREE.CanvasTexture(canvas);
    t.minFilter = t.magFilter = THREE.NearestFilter;
    return t;
  }, [canvas]);
  useEffect(() => {
    if (!hazard) return;
    const g = canvas.getContext("2d")!;
    const n = hazard.length;
    const cell = canvas.width / n;
    g.clearRect(0, 0, canvas.width, canvas.height);
    hazard.forEach((row, i) =>
      row.forEach((v, j) => {
        if (v <= -0.99) return; // the engine sends -1 for a tile with no data
        g.fillStyle = `hsla(${120 * (1 - Math.min(Math.abs(v) / 0.08, 1))}, 75%, 45%, 0.85)`;
        g.fillRect(j * cell + 1, i * cell + 1, cell - 2, cell - 2);
      }),
    );
    if (site) {
      g.strokeStyle = "#fff";
      g.lineWidth = 5;
      g.strokeRect(site[1] * cell + 4, site[0] * cell + 4, cell - 8, cell - 8);
    }
    texture.needsUpdate = true;
  }, [hazard, site, canvas, texture]);
  return texture;
}

// The simulator's boulders: lateral position as a fraction of 200 mm, radius and height in mm.
// These match SimScene in so/sources/sim.py, so the 3D view shows what the camera sees.
const BOULDERS = [[0.25, -0.15, 22, 30], [-0.35, 0.25, 18, 22]] as const;

// the values the scene eases toward each frame
type Smooth = { y: number; legacy: number; so: number; sigma: number; rf: number; nav: number; rfw: number; cam: number };

/** A floating label attached to a point in the scene. */
function Tag({ className, children }: { className: string; children: ReactNode }) {
  return (
    <Html zIndexRange={[4, 0]} style={{ pointerEvents: "none" }}>
      <div className={`tag ${className}`}>{children}</div>
    </Html>
  );
}

function Pip({ color, name, shown, out }: { color: string; name: string; shown: boolean; out: boolean }) {
  return (
    <>
      <mesh>
        <octahedronGeometry args={[0.075]} />
        <meshBasicMaterial color={out ? C.off : color} />
      </mesh>
      {shown && <Tag className={`tag-pip pip-${name.toLowerCase()} ${out ? "off" : ""}`}>{name}</Tag>}
    </>
  );
}

function Rig({ s }: { s: State }) {
  const shapes = useShapes();
  const site = s.scenario?.site ? `/sites/${s.scenario.site.split("/").pop()}` : "/textures/lro_moon.jpg";
  const groundTex = useGround(site);
  const hazardTex = useHazardTexture(s.hazard, s.site);
  const live = useRef(s);
  live.current = s;
  const eased = useRef<Smooth | null>(null);
  const camera = useThree((state) => state.camera);
  const controls = useThree((state) => state.controls) as { target: THREE.Vector3 } | null;

  // everything that moves is positioned in useFrame, not through React, so it animates smoothly
  const ref = {
    lander: useRef<THREE.Group>(null!),
    legacy: useRef<THREE.Group>(null!),
    so: useRef<THREE.Group>(null!),
    band: useRef<THREE.Mesh>(null!),
    beam: useRef<THREE.Group>(null!),
    beamLen: useRef<THREE.Group>(null!),
    beamEnd: useRef<THREE.Group>(null!),
    frustum: useRef<THREE.Group>(null!),
    pipNav: useRef<THREE.Group>(null!),
    pipRf: useRef<THREE.Group>(null!),
    pipCam: useRef<THREE.Group>(null!),
  };

  useFrame((_, dt) => {
    const s = live.current;
    const truth = s.truth ?? s.nav;
    const w = s.so.witness;
    const target: Smooth = {
      y: truth * U, // the true height above the ground
      legacy: (s.legacy.est ?? truth) * U,
      so: (s.so.est ?? truth) * U,
      sigma: Math.max(s.so.sigma ?? 0, 2) * U,
      rf: (s.rf ?? truth) * U,
      nav: (w.nav?.h ?? s.nav) * U,
      rfw: (w.rf?.h ?? s.rf ?? truth) * U,
      cam: (w.cam?.h ?? s.cam ?? truth) * U,
    };
    const c = (eased.current ??= { ...target });
    const k = 1 - Math.exp(-Math.min(dt, 0.1) * 12);
    (Object.keys(target) as (keyof Smooth)[]).forEach((key) => (c[key] += (target[key] - c[key]) * k));

    // A very tall replay (the HAKUTO-R broadcast is thousands of metres up) would leave the lander
    // out of frame, so the view rises with it. The rig and the simulator stay under 5.5 units.
    if (controls) {
      const lift = 2.3 + Math.max(c.y - 5.5, 0) - controls.target.y;
      controls.target.y += lift;
      camera.position.y += lift;
    }

    ref.lander.current.position.y = c.y;
    ref.legacy.current.position.y = c.legacy;
    ref.so.current.position.y = c.so;
    ref.band.current.position.y = c.so;
    ref.band.current.scale.y = c.sigma * 2;
    ref.beam.current.position.y = c.y;
    ref.beamLen.current.scale.y = c.rf;
    ref.beamEnd.current.position.y = -c.rf;
    ref.frustum.current.position.y = c.y;
    ref.frustum.current.scale.setScalar(Math.max(c.y, 0.05));
    ref.pipNav.current.position.y = c.nav;
    ref.pipRf.current.position.y = c.rfw;
    ref.pipCam.current.position.y = c.cam;
  });

  const truth = s.truth ?? s.nav;
  const rfOut = s.so.excluded.includes("rf");
  const camOut = s.so.excluded.includes("cam");
  const camOff = camOut || s.so.cam_abstain; // outvoted or just not locked: either way it's not voting
  const camColor = camOff ? C.off : C.cam;
  const err = (est: number | null) => (est == null || s.truth == null ? null : est - s.truth);
  const tone = (e: number | null) => (e != null && Math.abs(e) > ERR_BAD_MM ? "bad" : "");

  return (
    <>
      <mesh rotation-x={-Math.PI / 2} receiveShadow>
        <planeGeometry args={[GROUND, GROUND]} />
        {/* the key makes three.js rebuild the material once the texture arrives */}
        <meshStandardMaterial key={groundTex?.uuid} map={groundTex} bumpMap={groundTex} bumpScale={1.5} color={groundTex ? "#fff" : "#77777b"} roughness={1} />
      </mesh>

      {/* the simulator's boulders, where the camera sees them */}
      {s.kind === "sim" && BOULDERS.map(([bx, bz, radius, height]) => (
        <mesh key={bx} position={[bx * 200 * U, height * U * 0.4, bz * 200 * U]} scale={[radius * U, height * U * 0.6, radius * U]} castShadow receiveShadow>
          <dodecahedronGeometry args={[1, 1]} />
          <meshStandardMaterial color="#8b8b90" roughness={1} flatShading />
        </mesh>
      ))}

      <points geometry={shapes.starGeo}>
        <pointsMaterial color="#cfd6e4" size={0.28} transparent opacity={0.8} fog={false} />
      </points>

      {/* a ruler on the ground with one marker per witness, so you can read the votes off it */}
      <group position={[-1.25, 0, 1.25]}>
        <lineSegments geometry={shapes.ruler}>
          <lineBasicMaterial color={C.dim} transparent opacity={0.7} />
        </lineSegments>
        {[1, 2, 3, 4].map((y) => (
          <group key={y} position={[0, y, 0]}>
            <Tag className="tag-tick">{y * 100}</Tag>
          </group>
        ))}
        <group ref={ref.pipNav}><Pip color={C.nav} name="NAV" shown out={false} /></group>
        <group ref={ref.pipRf} visible={!!s.so.witness.rf}><Pip color={C.rf} name="RF" shown={!!s.so.witness.rf} out={rfOut} /></group>
        <group ref={ref.pipCam} visible={!!s.so.witness.cam}><Pip color={C.cam} name="CAM" shown={!!s.so.witness.cam} out={camOut} /></group>
      </group>

      <group ref={ref.lander}>
        <Lander />
        <Tag className="tag-lander tag-truth">TRUE {mm(truth)} {unit()}</Tag>
      </group>

      {/* the rangefinder beam is as long as the reading, so a wrong reading ends above or below the ground */}
      <group ref={ref.beam} position={[0.13, 0, 0]} visible={s.rf != null}>
        <group ref={ref.beamLen}>
          <mesh geometry={shapes.beam} scale={[0.012, 1, 0.012]} visible={!rfOut}>
            <meshBasicMaterial color={C.rf} />
          </mesh>
          {/* outvoted: dashed and drawn through the ground, to show where it thinks the surface is */}
          <lineSegments geometry={shapes.beamDash} visible={rfOut} renderOrder={9}>
            <lineDashedMaterial color={C.rf} dashSize={0.03} gapSize={0.03} depthTest={false} transparent opacity={0.8} />
          </lineSegments>
        </group>
        <group ref={ref.beamEnd}>
          <mesh rotation-x={-Math.PI / 2} renderOrder={10}>
            <ringGeometry args={[0.07, 0.11, 24]} />
            <meshBasicMaterial color={C.rf} side={THREE.DoubleSide} depthTest={false} transparent />
          </mesh>
        </group>
      </group>

      {/* the camera's view: cyan while it votes, grey when it abstains, dashed when it's outvoted */}
      <group ref={ref.frustum}>
        <lineSegments geometry={shapes.frustumLines}>
          {camOut
            ? <lineDashedMaterial color={C.dim} dashSize={0.04} gapSize={0.035} />
            : <lineBasicMaterial color={camColor} transparent opacity={camOff ? 0.6 : 0.9} />}
        </lineSegments>
        {/* the hazard grid, lying on the ground inside the camera's footprint (the frustum is one unit tall) */}
        {s.hazard && (
          <mesh position={[0, -1, 0]} rotation-x={-Math.PI / 2} renderOrder={3}>
            <planeGeometry args={[2 * FOV_W, 2 * FOV_D]} />
            <meshBasicMaterial map={hazardTex} transparent opacity={0.8} depthWrite={false} side={THREE.DoubleSide} />
          </mesh>
        )}
        <mesh geometry={shapes.frustumFaces}>
          <meshBasicMaterial color={camColor} transparent opacity={camOff ? 0.025 : 0.07} side={THREE.DoubleSide} depthWrite={false} />
        </mesh>
      </group>

      {/* what each brain believes, as a ghost lander. Subsidium's also has a band for its uncertainty. */}
      <group ref={ref.legacy} scale={1.16}>
        <Lander ghost={C.legacy} />
        <Tag className={`tag-lander tag-legacy ${tone(err(s.legacy.est))}`}>LEGACY {signed(err(s.legacy.est))} {unit()}</Tag>
      </group>
      <group ref={ref.so} scale={1.08}>
        <Lander ghost={C.so} />
        <Tag className={`tag-lander tag-so ${tone(err(s.so.est))}`}>SUBSIDIUM {signed(err(s.so.est))} {unit()}</Tag>
      </group>
      <mesh ref={ref.band}>
        <cylinderGeometry args={[0.78, 0.78, 1, 40, 1, true]} />
        <meshBasicMaterial color={C.so} transparent opacity={0.2} side={THREE.DoubleSide} depthWrite={false} />
      </mesh>
    </>
  );
}

/** If WebGL isn't available, show a message and not a broken page. */
class Boundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    return this.state.failed ? <div className="scene-fallback">3D view unavailable (no WebGL)</div> : this.props.children;
  }
}

export default function Scene3D({ s }: { s: State }) {
  return (
    <Boundary>
      <Canvas shadows dpr={[1, 1.75]} camera={{ position: [6.1, 4.1, 7.5], fov: 38, near: 0.1, far: 200 }}>
        <color attach="background" args={[C.bg]} />
        <fog attach="fog" args={[C.bg, 14, 34]} />
        <ambientLight intensity={0.35} />
        <directionalLight position={[-7, 6, 4]} intensity={2.6} castShadow shadow-mapSize={[1024, 1024]}
          shadow-camera-left={-6} shadow-camera-right={6} shadow-camera-top={6} shadow-camera-bottom={-6} shadow-camera-far={30} />
        <Rig s={s} />
        <OrbitControls makeDefault target={[0, 2.3, 0]} autoRotate autoRotateSpeed={0.45} enablePan={false} enableDamping
          minDistance={5} maxDistance={16} maxPolarAngle={Math.PI / 2 - 0.06} />
      </Canvas>
    </Boundary>
  );
}
