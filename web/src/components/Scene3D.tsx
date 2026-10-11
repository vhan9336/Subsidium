// The 3D view. One scene unit is 100 mm and y points up.
//
// The true lander sits at its real height. The ground under it is a block that rises and drops
// with the terrain (the rig's slide-in plateau), so "the ground fell away" is something you can
// see. Each brain's belief is a ghost lander drawn at ground + its estimate, so a ghost below the
// true lander means that brain thinks it's lower than it really is.
import { Edges, Html, OrbitControls } from "@react-three/drei";
import { Canvas, useFrame } from "@react-three/fiber";
import { Component, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import * as THREE from "three";
import { C, ERR_BAD_MM, mm, signed, unit } from "../theme";
import type { State } from "../types";

const U = 0.01; // scene units per mm
const PAD = 3; // side length of the terrain block under the lander
const DEPTH = 1.4; // how far the block reaches down
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

    // the ground is a big square with a hole where the terrain block sits, so the block can sink out of sight
    const h = PAD / 2;
    const ground = new THREE.Shape([[-20, -20], [20, -20], [20, 20], [-20, 20]].map(([x, y]) => new THREE.Vector2(x, y)));
    ground.holes.push(new THREE.Path([[-h, -h], [-h, h], [h, h], [h, -h]].map(([x, y]) => new THREE.Vector2(x, y))));
    return { frustumLines, frustumFaces, beam, beamDash, ruler: new THREE.BufferGeometry().setFromPoints(ticks),
             surface: new THREE.ShapeGeometry(ground) };
  }, []);
}

/**
 * The ground texture, repeating every TILE units and lined up with world coordinates, so the block
 * under the lander matches the ground around it. During a mission replay it's the real orbiter
 * photo of the crash site. Photos don't tile, so they're mirrored at the edges.
 */
function useGround(url: string, repeat: number, offset: number) {
  const [tex, setTex] = useState<THREE.Texture | null>(null);
  useEffect(() => {
    new THREE.TextureLoader().load(url, (t) => {
      t.colorSpace = THREE.SRGBColorSpace;
      t.wrapS = t.wrapT = THREE.MirroredRepeatWrapping;
      t.repeat.set(repeat, repeat);
      t.offset.set(offset, offset);
      setTex(t);
    });
  }, [url, repeat, offset]);
  return tex;
}

// the values the scene eases toward each frame
type Smooth = { y: number; g: number; legacy: number; so: number; sigma: number; rf: number; nav: number; rfw: number; cam: number };

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
  const surfaceTex = useGround(site, 1 / TILE, 0); // the big square is mapped straight from world coordinates
  const padTex = useGround(site, PAD / TILE, -PAD / 2 / TILE); // the block's plane is centred, so shift it to match
  const live = useRef(s);
  live.current = s;
  const eased = useRef<Smooth | null>(null);

  // everything that moves is positioned in useFrame, not through React, so it animates smoothly
  const ref = {
    lander: useRef<THREE.Group>(null!),
    block: useRef<THREE.Group>(null!),
    legacy: useRef<THREE.Group>(null!),
    so: useRef<THREE.Group>(null!),
    band: useRef<THREE.Mesh>(null!),
    beam: useRef<THREE.Group>(null!),
    beamLen: useRef<THREE.Group>(null!),
    beamEnd: useRef<THREE.Group>(null!),
    frustum: useRef<THREE.Group>(null!),
    ruler: useRef<THREE.Group>(null!),
    pipNav: useRef<THREE.Group>(null!),
    pipRf: useRef<THREE.Group>(null!),
    pipCam: useRef<THREE.Group>(null!),
  };

  useFrame((_, dt) => {
    const s = live.current;
    const truth = s.truth ?? s.nav;
    const w = s.so.witness;
    const target: Smooth = {
      y: s.nav_raw * U, // lander height above the ground as it was at reset
      g: (s.nav_raw - truth) * U, // where the ground under the lander is now
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

    ref.lander.current.position.y = c.y;
    ref.block.current.position.y = c.g;
    ref.legacy.current.position.y = c.g + c.legacy;
    ref.so.current.position.y = c.g + c.so;
    ref.band.current.position.y = c.g + c.so;
    ref.band.current.scale.y = c.sigma * 2;
    ref.beam.current.position.y = c.y;
    ref.beamLen.current.scale.y = c.rf;
    ref.beamEnd.current.position.y = -c.rf;
    ref.frustum.current.position.y = c.y;
    ref.frustum.current.scale.setScalar(Math.max(c.y - c.g, 0.05));
    ref.ruler.current.position.y = c.g;
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
      <mesh geometry={shapes.surface} rotation-x={-Math.PI / 2} receiveShadow>
        {/* the key makes three.js rebuild the material once the texture arrives */}
        <meshStandardMaterial key={surfaceTex?.uuid} map={surfaceTex} color={surfaceTex ? "#fff" : "#77777b"} roughness={1} />
      </mesh>

      {/* the terrain block under the lander. It moves with the plateau and shows the same ground texture. */}
      <group ref={ref.block}>
        <mesh rotation-x={-Math.PI / 2} position={[0, 0.002, 0]} receiveShadow>
          <planeGeometry args={[PAD, PAD]} />
          <meshStandardMaterial key={padTex?.uuid} map={padTex} color={padTex ? "#fff" : "#77777b"} roughness={1} />
        </mesh>
        <mesh position={[0, -DEPTH / 2, 0]}>
          <boxGeometry args={[PAD - 0.01, DEPTH, PAD - 0.01]} />
          <meshStandardMaterial color="#4a4c51" roughness={1} />
        </mesh>
      </group>

      {/* a ruler on the ground with one marker per witness, so you can read the votes off it */}
      <group ref={ref.ruler} position={[-1.25, 0, 1.25]}>
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
        <OrbitControls target={[0, 2.3, 0]} autoRotate autoRotateSpeed={0.45} enablePan={false} enableDamping
          minDistance={5} maxDistance={16} maxPolarAngle={Math.PI / 2 - 0.06} />
      </Canvas>
    </Boundary>
  );
}
