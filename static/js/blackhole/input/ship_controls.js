import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { input } from "./input_state.js";
import { getSurfaceHeight } from "../shared/physics_height.js";

const ray = new THREE.Raycaster();
const refPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const _hit = new THREE.Vector3();

export function updateShip(ship, camera, renderer, dt, time, activePlanets, config) {
  const conf = config;
  const w = renderer.domElement.clientWidth;
  const h = renderer.domElement.clientHeight;
  const cx = w / 2;
  const by = h - ship.state.boxBottom;

  if (ship.state.cursorX === undefined) ship.state.cursorX = cx;
  if (ship.state.cursorY === undefined) ship.state.cursorY = by - ship.state.boxHeight * 0.35;
  if (ship.state.velX === undefined) ship.state.velX = 0;

  // --- 1. FORWARD MOVEMENT ---
  // Defaults
  let targetForward = conf.baseSpeed;
  const boostSpeed = conf.boostSpeed || 120; // Default boost

  if (input.keys.has("ArrowDown")) {
    // Brake
    ship.state.speedPx -= conf.brakePower * dt;
    if (ship.state.speedPx < 0) ship.state.speedPx = 0;
  }
  else if (input.keys.has("ArrowUp")) {
    // [NEW] Boost
    targetForward = boostSpeed;
    const diff = targetForward - ship.state.speedPx;
    // Accelerate faster when boosting
    ship.state.speedPx += diff * 3.0 * dt;
  }
  else {
    // Cruising (Auto acceleration to base speed)
    const diff = targetForward - ship.state.speedPx;
    ship.state.speedPx += diff * 2.0 * dt;
  }

  // --- 2. LATERAL ---
  let dirX = 0;
  if (input.keys.has("ArrowLeft")) dirX -= 1;
  if (input.keys.has("ArrowRight")) dirX += 1;

  const targetVelX = dirX * conf.maxLateralSpeed;
  const isAccelerating = (dirX !== 0 && Math.sign(dirX) === Math.sign(ship.state.velX));
  const rate = isAccelerating ? conf.lateralAccel : conf.lateralFriction;

  const alpha = 1.0 - Math.exp(-rate * dt);
  ship.state.velX += (targetVelX - ship.state.velX) * alpha;

  // --- 3. BOUNDARY ---
  const halfBox = ship.state.boxWidth / 2;
  const minX = cx - halfBox;
  const maxX = cx + halfBox;

  ship.state.cursorX += ship.state.velX * dt;

  if (ship.state.cursorX < minX) {
      ship.state.cursorX = minX;
      ship.state.velX *= -0.2;
  }
  if (ship.state.cursorX > maxX) {
      ship.state.cursorX = maxX;
      ship.state.velX *= -0.2;
  }

  const minY = by - ship.state.boxHeight;
  const maxY = by;
  ship.state.cursorY = Math.max(minY, Math.min(maxY, ship.state.cursorY));

  // --- 4. RAYCAST & POSITION ---
  const ndcX = Math.max(-1, Math.min(1, (ship.state.cursorX / w) * 2 - 1));
  const ndcY = -(ship.state.cursorY / h) * 2 + 1;

  ray.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
  refPlane.constant = 0;

  if (ray.ray.intersectPlane(refPlane, _hit)) {
    const targetX = _hit.x;
    const currentZ = ship.mesh.position.z;
    const h1 = getSurfaceHeight(targetX, currentZ, time, activePlanets);
    const newZ = currentZ - ship.state.speedPx * dt;

    ship.mesh.position.set(targetX, h1 + conf.hoverOffset, newZ);
    ship.state.y = h1 + conf.hoverOffset;

    // Visuals
    const bankFactor = THREE.MathUtils.clamp(ship.state.velX / conf.maxLateralSpeed, -1, 1);
    const targetRoll = -bankFactor * 0.78;
    const targetYaw = (Math.PI / 4) - (bankFactor * 0.4);
    const rotLerp = 4.0 * dt;

    ship.mesh.rotation.z += (targetRoll - ship.mesh.rotation.z) * rotLerp;
    ship.mesh.rotation.y += (targetYaw - ship.mesh.rotation.y) * rotLerp;
  }
}