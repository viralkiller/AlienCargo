import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { input } from "./input_state.js";
import { getSurfaceHeight } from "../shared/physics_height.js";

const ray = new THREE.Raycaster();
const refPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const _hit = new THREE.Vector3();

const DEFAULT_CONFIG = {
  baseSpeed: 90,
  brakePower: 150,
  hoverOffset: 4.0,
  maxLateralSpeed: 100
};

export function updateShip(ship, camera, renderer, dt, activePlanets, config) {
  // Use config or fallbacks
  const conf = config || DEFAULT_CONFIG;

  const w = renderer.domElement.clientWidth;
  const h = renderer.domElement.clientHeight;

  // Center Screen
  const cx = w / 2;
  const by = h - ship.state.boxBottom;

  if (ship.state.cursorX === undefined) ship.state.cursorX = cx;
  if (ship.state.cursorY === undefined) ship.state.cursorY = by - ship.state.boxHeight * 0.35;

  // --- SPEED CONTROL ---
  let targetSpeed = conf.baseSpeed;

  if (input.keys.has("ArrowDown")) {
    ship.state.speedPx -= conf.brakePower * dt;
    if (ship.state.speedPx < 10) ship.state.speedPx = 10;
  } else {
    ship.state.speedPx = targetSpeed;
  }

  // --- LATERAL CONTROLS ---
  let dx = 0;
  if (input.keys.has("ArrowLeft")) dx -= 1;
  if (input.keys.has("ArrowRight")) dx += 1;

  if (dx !== 0) {
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

    ship.state.cursorX += dx * conf.maxLateralSpeed * lateralFactor * dt;

    // Clamp X
    const minX = cx - halfW;
    const maxX = cx + halfW;
    ship.state.cursorX = Math.max(minX, Math.min(maxX, ship.state.cursorX));
  }

  // Clamp Y
  const minY = by - ship.state.boxHeight;
  const maxY = by;
  ship.state.cursorY = Math.max(minY, Math.min(maxY, ship.state.cursorY));

  // --- RAYCAST & POSITION UPDATE ---
  ray.setFromCamera(
    new THREE.Vector2((ship.state.cursorX / w) * 2 - 1, -(ship.state.cursorY / h) * 2 + 1),
    camera
  );
  refPlane.constant = 0;

  if (ray.ray.intersectPlane(refPlane, _hit)) {
    const targetX = _hit.x;
    const currentZ = ship.mesh.position.z;

    const h1 = getSurfaceHeight(targetX, currentZ, activePlanets);
    const newZ = currentZ - ship.state.speedPx * dt;

    ship.mesh.position.set(targetX, h1 + conf.hoverOffset, newZ);
    ship.state.y = h1 + conf.hoverOffset;
  }
}