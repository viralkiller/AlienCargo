import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { input } from "./input_state.js";
import { getSurfaceHeight } from "../shared/physics_height.js";

const ray = new THREE.Raycaster();
const refPlane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const _hit = new THREE.Vector3();

// [TUNING] River Physics Constants
const GRAVITY_G = 35.0; // Strength of the pull
const WHIRLPOOL_BIAS = 0.15; // How much it spins vs sucks (0.0 = pure suck)

export function updateShip(ship, camera, renderer, dt, time, activePlanets, config) {
  const conf = config;
  const w = renderer.domElement.clientWidth;
  const h = renderer.domElement.clientHeight;
  const cx = w / 2;
  const by = h - ship.state.boxBottom;

  if (ship.state.cursorX === undefined) ship.state.cursorX = cx;
  if (ship.state.cursorY === undefined) ship.state.cursorY = by - ship.state.boxHeight * 0.35;
  if (ship.state.velX === undefined) ship.state.velX = 0;

  // --- 0. CALCULATE RIVER PHYSICS (The Drift) ---
  let flowX = 0;
  let flowZ = 0;

  // Iterate all active gravity wells
  if (activePlanets) {
    for (const p of activePlanets) {
        const dx = p.position.x - ship.mesh.position.x;
        const dz = p.position.z - ship.mesh.position.z;
        const distSq = dx*dx + dz*dz;
        const dist = Math.sqrt(distSq);

        // Skip if too far (Optimization) or too close (Singularity)
        if (dist > 150 || dist < 1.0) continue;

        // River Model: v = -sqrt(2GM/r)
        // Vector points TOWARDS planet (dx, dz)
        const vMag = Math.sqrt((2.0 * GRAVITY_G * p.userData.mass) / dist);

        // Normalized Directions
        const nx = dx / dist;
        const nz = dz / dist;

        // Whirlpool: Tangent vector (-nz, nx)
        const tx = -nz;
        const tz = nx;

        // Combine Radial (Suck) and Tangential (Spin)
        // Note: We flip tangent sign based on which side of the center line we are?
        // No, consistent spin direction (Counter-Clockwise) looks best.
        const fx = nx * (1.0 - WHIRLPOOL_BIAS) + tx * WHIRLPOOL_BIAS;
        const fz = nz * (1.0 - WHIRLPOOL_BIAS) + tz * WHIRLPOOL_BIAS;

        flowX += fx * vMag;
        flowZ += fz * vMag;
    }
  }

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
    // Boost
    targetForward = boostSpeed;
    const diff = targetForward - ship.state.speedPx;
    ship.state.speedPx += diff * 3.0 * dt;
  }
  else {
    // Cruising
    const diff = targetForward - ship.state.speedPx;
    ship.state.speedPx += diff * 2.0 * dt;
  }

  // --- 2. LATERAL MOVEMENT ---
  let dirX = 0;
  if (input.keys.has("ArrowLeft")) dirX -= 1;
  if (input.keys.has("ArrowRight")) dirX += 1;

  const targetVelX = dirX * conf.maxLateralSpeed;
  const isAccelerating = (dirX !== 0 && Math.sign(dirX) === Math.sign(ship.state.velX));
  const rate = isAccelerating ? conf.lateralAccel : conf.lateralFriction;

  const alpha = 1.0 - Math.exp(-rate * dt);
  ship.state.velX += (targetVelX - ship.state.velX) * alpha;

  // --- 3. APPLY PHYSICS DRIFT ---
  // A. Apply Z-Drift (World Space)
  // Ship moves negative Z naturally.
  // If flowZ is negative (pulling forward into a planet ahead), it adds speed.
  // If flowZ is positive (pulling back to a planet behind), it slows us.
  const zDrift = flowZ * dt;

  // B. Apply X-Drift (Input Space Injection)
  // We need to fight the current. The current pushes the SHIP (World X).
  // But the ship's X is determined by `cursorX` (Screen Pixels).
  // To simulate the ship being pushed, we must offset `cursorX` in the direction of the flow.
  if (Math.abs(flowX) > 0.1) {
      // Approximate World->Screen Ratio at Ship Depth
      // Camera Y=18, Ship Y=3 -> Delta Y = 15. FOV 60.
      // Visible Height = 2 * 15 * tan(30) = 30 * 0.577 = 17.31
      // Aspect ~1.77 -> Visible Width ~30.6
      // If Screen Width = 1920, Ratio ~ 62 px/unit.
      // We calculate purely:
      const distCamShip = Math.abs(camera.position.z - ship.mesh.position.z); // Approx
      const visibleHeight = 2.0 * distCamShip * Math.tan((camera.fov * Math.PI / 180) / 2);
      const visibleWidth = visibleHeight * camera.aspect;
      const pxPerUnit = w / visibleWidth;

      const screenDrift = flowX * dt * pxPerUnit;
      ship.state.cursorX += screenDrift;
  }

  // --- 4. BOUNDARY ---
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

  // --- 5. RAYCAST & POSITION ---
  const ndcX = Math.max(-1, Math.min(1, (ship.state.cursorX / w) * 2 - 1));
  const ndcY = -(ship.state.cursorY / h) * 2 + 1;

  ray.setFromCamera(new THREE.Vector2(ndcX, ndcY), camera);
  refPlane.constant = 0;

  if (ray.ray.intersectPlane(refPlane, _hit)) {
    const targetX = _hit.x;

    // Calculate new Z based on engine speed + river drift
    const currentZ = ship.mesh.position.z;
    const newZ = currentZ - (ship.state.speedPx * dt) + zDrift;

    const h1 = getSurfaceHeight(targetX, newZ, time, activePlanets);

    ship.mesh.position.set(targetX, h1 + conf.hoverOffset, newZ);
    ship.state.y = h1 + conf.hoverOffset;

    // Visuals: Bank and Yaw
    // We add flowX to the banking calculation so the ship "leans" into the current
    const totalLateralForce = (ship.state.velX / conf.maxLateralSpeed) + (flowX * 0.05);

    const bankFactor = THREE.MathUtils.clamp(totalLateralForce, -1, 1);
    const targetRoll = -bankFactor * 0.78;
    const targetYaw = (Math.PI / 4) - (bankFactor * 0.4);

    const rotLerp = 4.0 * dt;
    ship.mesh.rotation.z += (targetRoll - ship.mesh.rotation.z) * rotLerp;
    ship.mesh.rotation.y += (targetYaw - ship.mesh.rotation.y) * rotLerp;
  }
}