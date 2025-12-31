import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

const _desiredPos = new THREE.Vector3();
const _lookAt = new THREE.Vector3();

export function updateChaseCamera(camera, ship, dt) {
  const shipYaw = ship.mesh.rotation.y - Math.PI / 4;

  const camHeight = 80.0;

  // [FIX] Move camera further back (50 -> 70)
  // This pulls the view back so the ship isn't trapped at the bottom edge.
  const camBack = 70.0;

  const laneFollowRatio = 0.8;

  const targetY = Math.max(ship.mesh.position.y + camHeight, 60.0);

  _desiredPos.set(
    ship.mesh.position.x * laneFollowRatio,
    targetY,
    ship.mesh.position.z + camBack
  );

  // [FIX] Reduce lookAhead slightly (180 -> 150)
  // This pitches the camera down a tiny bit to bring the ship up-screen,
  // but keeps it high enough to see the horizon.
  const lookAhead = 150.0;

  _lookAt.set(
      ship.mesh.position.x * (laneFollowRatio * 0.9),
      ship.mesh.position.y,
      ship.mesh.position.z - lookAhead
  );

  const follow = 1.0 - Math.pow(0.0001, dt);
  camera.position.lerp(_desiredPos, follow);
  camera.lookAt(_lookAt);

  const targetCamRoll = ship.mesh.rotation.z * 0.4;
  camera.rotation.z += (targetCamRoll - camera.rotation.z) * 1.5 * dt;
}