import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { input } from "./input_state.js";

const ray = new THREE.Raycaster();
const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const _hit = new THREE.Vector3();

// [Constraint] The warped grid has terrain noise peaks up to ~7.0 units high.
// We set the ship flight height to 10.0 to ensure it never clips or disappears below the grid.
const SAFE_FLIGHT_HEIGHT = 10.0;

export function updateShip(ship, camera, renderer, dt) {
  // Ensure the state reflects our safe height (so asteroids/logic sync up)
  ship.state.y = SAFE_FLIGHT_HEIGHT;

  const w = renderer.domElement.clientWidth;
  const h = renderer.domElement.clientHeight;

  // Bottom control box anchor (screen space)
  const cx = w / 2;
  const by = h - ship.state.boxBottom;

  // Persistent cursor inside box (screen space)
  if (ship.state.cursorX === undefined) ship.state.cursorX = cx;
  if (ship.state.cursorY === undefined) ship.state.cursorY = by - ship.state.boxHeight * 0.35;

  let dx = 0;
  let dy = 0;

  if (input.keys.has("ArrowLeft")) dx -= 1;
  if (input.keys.has("ArrowRight")) dx += 1;
  // Up moves the cursor UP (screen) => Forward (world)
  if (input.keys.has("ArrowUp")) dy -= 1;
  // [Constraint] No back allowed
  // if (input.keys.has("ArrowDown")) dy += 1;

  // Only calculate movement logic if inputs exist
  if (dx || dy) {
    const len = Math.hypot(dx, dy) || 1;
    dx /= len;
    dy /= len;

    // --- Quadratic Lateral Effort ---
    // 1. We restrict the allowed width significantly (50% of the red box).
    const allowedWidth = ship.state.boxWidth * 0.5;
    const halfW = allowedWidth / 2;

    // 2. Calculate distance from center (0.0 to 1.0)
    const distFromCenter = ship.state.cursorX - cx;
    const distRatio = Math.min(1.0, Math.abs(distFromCenter) / halfW);

    // 3. If moving OUTWARDS, apply resistance.
    // Moving left (dx < 0) when already on left (dist < 0) -> Resistance
    const movingOut = (dx < 0 && distFromCenter < 0) || (dx > 0 && distFromCenter > 0);

    let lateralFactor = 0.5; // Base lateral speed (slower than forward)

    if (movingOut) {
      // Effort increases quadratically: Speed approaches 0 as we near the edge.
      // Curve: 1 - r^2
      const resistance = 1.0 - (distRatio * distRatio);
      lateralFactor *= Math.max(0.01, resistance);
    }

    const pxPerSec = ship.state.speedPx;
    ship.state.cursorX += dx * pxPerSec * lateralFactor * dt;
    ship.state.cursorY += dy * pxPerSec * dt;

    // --- Clamping ---
    // Hard clamp to the tighter width
    const minX = cx - halfW;
    const maxX = cx + halfW;
    ship.state.cursorX = Math.max(minX, Math.min(maxX, ship.state.cursorX));

    // Clamp Y to box bounds
    const minY = by - ship.state.boxHeight;
    const maxY = by;
    ship.state.cursorY = Math.max(minY, Math.min(maxY, ship.state.cursorY));

    // Safety window clamp
    ship.state.cursorX = Math.max(0, Math.min(w, ship.state.cursorX));
    ship.state.cursorY = Math.max(0, Math.min(h, ship.state.cursorY));
  }

  // --- Raycast / Position Update ---
  // We run this EVERY frame (even if no input) to ensure the ship stays
  // at the correct SAFE_FLIGHT_HEIGHT and doesn't sink into the grid.

  ray.setFromCamera(
    new THREE.Vector2((ship.state.cursorX / w) * 2 - 1, -(ship.state.cursorY / h) * 2 + 1),
    camera
  );

  // Plane at y = 10.0
  plane.constant = -SAFE_FLIGHT_HEIGHT;

  if (ray.ray.intersectPlane(plane, _hit)) {
    ship.mesh.position.set(_hit.x, SAFE_FLIGHT_HEIGHT, _hit.z);

    // Optional debug throttling
    if (Math.random() < 0.01 && (dx || dy)) {
       console.log("[SHIP] Pos:", _hit.x.toFixed(1), _hit.z.toFixed(1));
    }
  }
}