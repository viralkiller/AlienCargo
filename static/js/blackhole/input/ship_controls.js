import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { input } from "./input_state.js";
import { getSurfaceHeight } from "../shared/physics_height.js";

const ray = new THREE.Raycaster();
const refPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const _hit = new THREE.Vector3();

const HOVER_OFFSET = 2.5;

// Physics Tuning
const BASE_SPEED = 100;    // Minimum speed
const MAX_SPEED = 400;     // Cap speed
const GRAVITY_ASSIST = 25.0; // How much slopes accelerate you
const FRICTION = 0.98;     // Gradual slowdown back to base speed

export function updateShip(ship, camera, renderer, dt, activePlanets) {
  const w = renderer.domElement.clientWidth;
  const h = renderer.domElement.clientHeight;

  // Center Screen
  const cx = w / 2;
  const by = h - ship.state.boxBottom;

  if (ship.state.cursorX === undefined) ship.state.cursorX = cx;
  if (ship.state.cursorY === undefined) ship.state.cursorY = by - ship.state.boxHeight * 0.35;

  // --- LATERAL CONTROLS ONLY (Left/Right) ---
  let dx = 0;
  if (input.keys.has("ArrowLeft")) dx -= 1;
  if (input.keys.has("ArrowRight")) dx += 1;
  // Note: Up/Down no longer affect speed manually.
  // Momentum is now derived from the terrain.

  // --- LATERAL MOVEMENT ---
  if (dx) {
    const allowedWidth = ship.state.boxWidth * 0.5;
    const halfW = allowedWidth / 2;
    const distFromCenter = ship.state.cursorX - cx;
    const distRatio = Math.min(1.0, Math.abs(distFromCenter) / halfW);
    const movingOut = (dx < 0 && distFromCenter < 0) || (dx > 0 && distFromCenter > 0);

    let lateralFactor = 0.5;
    if (movingOut) {
      const resistance = 1.0 - (distRatio * distRatio);
      lateralFactor *= Math.max(0.01, resistance);
    }

    // We use a fixed reference speed for cursor responsiveness
    // independent of the actual forward speed (so controls don't get twitchy at high speed)
    const cursorSpeed = 140;
    ship.state.cursorX += dx * cursorSpeed * lateralFactor * dt;

    // Clamp X
    const minX = cx - halfW;
    const maxX = cx + halfW;
    ship.state.cursorX = Math.max(minX, Math.min(maxX, ship.state.cursorX));
  }

  // Clamp Y (Visual only, controls pitch/visual box)
  const minY = by - ship.state.boxHeight;
  const maxY = by;
  ship.state.cursorY = Math.max(minY, Math.min(maxY, ship.state.cursorY));

  // --- RAYCAST FOR LATERAL POSITION ---
  ray.setFromCamera(
    new THREE.Vector2((ship.state.cursorX / w) * 2 - 1, -(ship.state.cursorY / h) * 2 + 1),
    camera
  );
  refPlane.constant = 0;

  // We need to calculate where the ray hits the plane X-wise.
  // We ignore Z from the ray because Z is now Auto-Forward.
  if (ray.ray.intersectPlane(refPlane, _hit)) {
    const targetX = _hit.x;

    // --- SLOPE PHYSICS & AUTO FORWARD ---

    // 1. Get current height
    const currentZ = ship.mesh.position.z;
    const h1 = getSurfaceHeight(targetX, currentZ, activePlanets);

    // 2. Look ahead slightly to measure slope
    const lookAheadDist = 2.0;
    const h2 = getSurfaceHeight(targetX, currentZ - lookAheadDist, activePlanets);

    // 3. Slope: Positive if going downhill (h1 > h2), Negative if uphill
    const slope = (h1 - h2);

    // 4. Apply Slope to Speed
    // If slope > 0 (Downhill), speed increases.
    // If slope < 0 (Uphill), speed decreases.
    ship.state.speedPx += slope * GRAVITY_ASSIST;

    // 5. Friction / Limits
    // Apply friction to return to Base Speed naturally
    if (ship.state.speedPx > BASE_SPEED) {
      ship.state.speedPx *= FRICTION;
    }
    // Hard Clamp
    ship.state.speedPx = Math.max(BASE_SPEED, Math.min(MAX_SPEED, ship.state.speedPx));

    // --- UPDATE POSITION ---
    // Move Forward (-Z)
    const newZ = currentZ - ship.state.speedPx * dt;

    // Update Mesh
    ship.mesh.position.set(targetX, h1 + HOVER_OFFSET, newZ);
    ship.state.y = h1 + HOVER_OFFSET;

    // Optional Debug: Visualize speed
    if (Math.random() < 0.02) {
       console.log("[PHYSICS] Slope:", slope.toFixed(2), "Speed:", ship.state.speedPx.toFixed(0));
    }
  }
}