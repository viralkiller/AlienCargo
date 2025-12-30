import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

const _desiredPos = new THREE.Vector3();
const _lookAt = new THREE.Vector3();
const _forward = new THREE.Vector3(0, 0, -1);

export function updateChaseCamera(camera, ship, dt) {
  // 1. Calculate Ship Forward Vector
  const shipYaw = ship.mesh.rotation.y - Math.PI / 4;

  // 2. Camera Offset
  const camHeight = 18.0;
  const camBack = 35.0;

  // [TUNING]
  // 0.8 = Camera follows 80% of ship's lateral movement.
  // This keeps the ship mostly centered, allowing you to venture far into the terrain
  // without the ship disappearing off the side of the screen.
  const laneFollowRatio = 0.8;

  _desiredPos.set(
    ship.mesh.position.x * laneFollowRatio,
    ship.mesh.position.y + camHeight,
    ship.mesh.position.z + camBack
  );

  const lookAhead = 100.0;

  // Blend look-target
  _lookAt.set(
      ship.mesh.position.x * (laneFollowRatio * 0.9),
      ship.mesh.position.y,
      ship.mesh.position.z - lookAhead
  );

  // 3. Smooth Follow (Dampening)
  // Lowered the power base slightly for a "heavier", smoother camera
  const follow = 1.0 - Math.pow(0.0001, dt);
  camera.position.lerp(_desiredPos, follow);
  camera.lookAt(_lookAt);

  // 4. Dynamic Camera Banking
  // Smoother roll lerp
  const targetCamRoll = ship.mesh.rotation.z * 0.4;
  camera.rotation.z += (targetCamRoll - camera.rotation.z) * 1.5 * dt;
}