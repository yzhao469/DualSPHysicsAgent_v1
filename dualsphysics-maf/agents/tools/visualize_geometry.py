"""Three.js geometry visualization tool — generates a self-contained HTML file
showing the DebrisFlow2D domain setup and opens it in the user's browser."""

import json
import platform
import subprocess
import tempfile
import webbrowser
from pathlib import Path


def _is_wsl() -> bool:
    """Detect if running inside WSL."""
    try:
        return "microsoft" in platform.uname().release.lower()
    except Exception:
        return False


def _open_in_browser(file_path: Path) -> None:
    """Open an HTML file in the user's default browser, with WSL2 support."""
    if _is_wsl():
        try:
            win_path = subprocess.check_output(
                ["wslpath", "-w", str(file_path)], text=True
            ).strip()
            subprocess.Popen(
                ["cmd.exe", "/c", "start", "", win_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except FileNotFoundError:
            pass
    webbrowser.open(file_path.as_uri())

_HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>DebrisFlow2D Geometry Preview</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { background: #1a1a2e; overflow: hidden; font-family: 'Segoe UI', system-ui, sans-serif; }
  canvas { display: block; }
  #info {
    position: absolute; top: 16px; left: 16px;
    color: #e0e0e0; font-size: 13px; line-height: 1.6;
    background: rgba(0,0,0,0.6); padding: 14px 18px; border-radius: 8px;
    max-width: 320px; pointer-events: none;
  }
  #info h2 { font-size: 15px; margin-bottom: 6px; color: #4fc3f7; }
  #info .label { color: #90caf9; }
  #legend {
    position: absolute; bottom: 16px; left: 16px;
    color: #e0e0e0; font-size: 12px;
    background: rgba(0,0,0,0.6); padding: 10px 14px; border-radius: 8px;
    pointer-events: none;
  }
  #legend div { display: flex; align-items: center; margin: 3px 0; }
  #legend .swatch {
    width: 14px; height: 14px; border-radius: 3px; margin-right: 8px;
    display: inline-block;
  }
</style>
</head>
<body>
<div id="info">
  <h2>DebrisFlow2D — Geometry Preview</h2>
  <span class="label">Channel:</span> CHANNEL_LENGTH m &times; CHANNEL_HEIGHT m<br>
  <span class="label">Fluid column:</span> FLUID_SIZE_X m &times; FLUID_SIZE_Z m<br>
  <span class="label">Probes:</span> NUM_PROBES points<br>
  <span class="label">dp:</span> DP_VAL m
</div>
<div id="legend">
  <div><span class="swatch" style="background:#42a5f5"></span> Fluid column</div>
  <div><span class="swatch" style="background:#78909c"></span> Boundary walls</div>
  <div><span class="swatch" style="background:#ef5350"></span> Probe points</div>
</div>

<script type="importmap">
{
  "imports": {
    "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
  }
}
</script>

<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { FontLoader } from 'three/addons/loaders/FontLoader.js';

// ---- Geometry data injected by Python ----
const FLUID_ORIGIN = FLUID_ORIGIN_JSON;
const FLUID_SIZE   = FLUID_SIZE_JSON;
const CHANNEL_LEN  = CHANNEL_LENGTH_VAL;
const CHANNEL_HT   = CHANNEL_HEIGHT_VAL;
const WALL_THICK   = 0.04;
const PROBE_XS     = PROBE_XS_JSON;
const PROBE_ZS     = PROBE_ZS_JSON;
const DEPTH        = 0.3;  // visual y-depth for 3D appearance

// ---- Scene setup ----
const scene    = new THREE.Scene();
scene.background = new THREE.Color(0x1a1a2e);

const aspect = window.innerWidth / window.innerHeight;
const camera = new THREE.PerspectiveCamera(45, aspect, 0.1, 100);
const cx = CHANNEL_LEN / 2;
const cz = CHANNEL_HT / 2;
camera.position.set(cx, 2.5, cz + 3.5);
camera.lookAt(cx, 0, cz);

const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.target.set(cx, 0, cz);
controls.enableDamping = true;
controls.dampingFactor = 0.08;
controls.update();

// ---- Lights ----
scene.add(new THREE.AmbientLight(0xffffff, 0.6));
const dirLight = new THREE.DirectionalLight(0xffffff, 0.8);
dirLight.position.set(5, 8, 5);
scene.add(dirLight);

// ---- Materials ----
const fluidMat = new THREE.MeshPhongMaterial({
  color: 0x42a5f5, transparent: true, opacity: 0.55, side: THREE.DoubleSide
});
const wallMat = new THREE.MeshPhongMaterial({
  color: 0x78909c, transparent: true, opacity: 0.7
});
const probeMat = new THREE.MeshPhongMaterial({ color: 0xef5350 });
const edgeMat  = new THREE.LineBasicMaterial({ color: 0x263238 });

function addBox(sx, sy, sz, px, py, pz, mat) {
  const geo  = new THREE.BoxGeometry(sx, sy, sz);
  const mesh = new THREE.Mesh(geo, mat);
  // BoxGeometry is centred; shift so (px,py,pz) is the min corner
  mesh.position.set(px + sx/2, py + sy/2, pz + sz/2);
  scene.add(mesh);
  const edges = new THREE.EdgesGeometry(geo);
  const line  = new THREE.LineSegments(edges, edgeMat);
  line.position.copy(mesh.position);
  scene.add(line);
  return mesh;
}

// ---- Fluid column ----
addBox(FLUID_SIZE[0], DEPTH, FLUID_SIZE[1],
       FLUID_ORIGIN[0], 0, FLUID_ORIGIN[1], fluidMat);

// ---- Floor (mk=11) ----
addBox(CHANNEL_LEN, DEPTH, WALL_THICK,  0, 0, 0, wallMat);

// ---- Left wall (mk=12) ----
addBox(WALL_THICK, DEPTH, CHANNEL_HT,  0, 0, 0, wallMat);

// ---- Right wall (mk=13) ----
addBox(WALL_THICK, DEPTH, CHANNEL_HT,  CHANNEL_LEN - WALL_THICK, 0, 0, wallMat);

// ---- Probe points ----
const probeGeo = new THREE.SphereGeometry(0.03, 16, 16);
for (const x of PROBE_XS) {
  for (const z of PROBE_ZS) {
    const sphere = new THREE.Mesh(probeGeo, probeMat);
    sphere.position.set(x, DEPTH / 2, z);
    scene.add(sphere);
  }
}

// ---- Grid helper (on x-z plane) ----
const gridSize = Math.ceil(Math.max(CHANNEL_LEN, CHANNEL_HT) + 1);
const grid = new THREE.GridHelper(gridSize, gridSize * 4, 0x444466, 0x333355);
grid.position.set(gridSize / 2, -0.001, gridSize / 2);
scene.add(grid);

// ---- Axis arrows ----
const axLen = Math.max(CHANNEL_LEN, CHANNEL_HT) * 0.15;
scene.add(new THREE.ArrowHelper(
  new THREE.Vector3(1,0,0), new THREE.Vector3(-0.2, 0, -0.2), axLen, 0xff5555, 0.06, 0.04));
scene.add(new THREE.ArrowHelper(
  new THREE.Vector3(0,0,1), new THREE.Vector3(-0.2, 0, -0.2), axLen, 0x55ff55, 0.06, 0.04));

// ---- Dimension lines ----
function addDimLine(x1, z1, x2, z2, color) {
  const pts = [new THREE.Vector3(x1, DEPTH + 0.02, z1),
               new THREE.Vector3(x2, DEPTH + 0.02, z2)];
  const geo  = new THREE.BufferGeometry().setFromPoints(pts);
  const line = new THREE.Line(geo, new THREE.LineBasicMaterial({color}));
  scene.add(line);
}
// Channel length
addDimLine(0, -0.08, CHANNEL_LEN, -0.08, 0xffcc80);
// Fluid width
addDimLine(FLUID_ORIGIN[0], FLUID_SIZE[1] + 0.08,
           FLUID_ORIGIN[0] + FLUID_SIZE[0], FLUID_SIZE[1] + 0.08, 0x80d8ff);
// Fluid height
addDimLine(FLUID_ORIGIN[0] + FLUID_SIZE[0] + 0.08, FLUID_ORIGIN[1],
           FLUID_ORIGIN[0] + FLUID_SIZE[0] + 0.08, FLUID_ORIGIN[1] + FLUID_SIZE[1], 0x80d8ff);

// ---- Animate ----
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();

window.addEventListener('resize', () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
});
</script>
</body>
</html>"""


def visualize_geometry(
    fluid_size_x: float,
    fluid_size_z: float,
    channel_length: float,
    channel_height: float,
    probe_xs: list,
    probe_zs: list,
    dp: float = 0.01,
) -> str:
    """Generate and open an interactive 3D visualization of the DebrisFlow2D geometry.

    Shows the fluid column, boundary walls, and probe point locations in the
    browser using Three.js. The user can orbit, zoom, and pan.

    Call this when the user requests to see the geometry visualization
    (e.g., they reply 'viz' during the parameter review).

    Args:
        fluid_size_x:   Width of the fluid column (m).
        fluid_size_z:   Height of the fluid column (m).
        channel_length: Length of the channel floor (m).
        channel_height: Height of the side walls (m).
        probe_xs:       List of probe x-coordinates (m).
        probe_zs:       List of probe z-coordinates (m).
        dp:             Particle spacing (m), shown in info panel.

    Returns:
        A message confirming the visualization was opened.
    """
    html = _HTML_TEMPLATE
    html = html.replace("FLUID_ORIGIN_JSON", json.dumps([0.0, 0.0]))
    html = html.replace("FLUID_SIZE_JSON", json.dumps([fluid_size_x, fluid_size_z]))
    html = html.replace("CHANNEL_LENGTH_VAL", str(channel_length))
    html = html.replace("CHANNEL_HEIGHT_VAL", str(channel_height))
    html = html.replace("PROBE_XS_JSON", json.dumps(probe_xs))
    html = html.replace("PROBE_ZS_JSON", json.dumps(probe_zs))
    # Info panel text
    html = html.replace("CHANNEL_LENGTH", str(channel_length))
    html = html.replace("CHANNEL_HEIGHT", str(channel_height))
    html = html.replace("FLUID_SIZE_X", str(fluid_size_x))
    html = html.replace("FLUID_SIZE_Z", str(fluid_size_z))
    html = html.replace("NUM_PROBES", str(len(probe_xs) * len(probe_zs)))
    html = html.replace("DP_VAL", str(dp))

    out_path = Path(tempfile.mkdtemp(prefix="dsph_viz_")) / "geometry_preview.html"
    out_path.write_text(html, encoding="utf-8")
    _open_in_browser(out_path)

    return (
        f"Geometry visualization opened in browser: {out_path}\n"
        f"Shows: fluid column {fluid_size_x}x{fluid_size_z} m, "
        f"channel {channel_length}x{channel_height} m, "
        f"{len(probe_xs) * len(probe_zs)} probe points."
    )
