import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

const _desiredPos = new THREE.Vector3();
const _lookAt = new THREE.Vector3();
// Forward vector (Standard OpenGL -Z)
const _forward = new THREE.Vector3(0, 0, -1);

export function updateChaseCamera(camera, ship, dt) {
  // Ship forward from its yaw (for lookahead)
  const shipYaw = ship.mesh.rotation.y - Math.PI / 4;
  const shipForward = _forward.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), shipYaw);

  // Camera offset
  const camHeight = 18.0;
  const camBack = 35.0;

  // [FIX] Lock Camera X to 0.
  // Previously: ship.mesh.position.x (Camera strafed with ship)
  // Now: 0 (Camera stays centered on the 'lane', ship moves inside the view)
  _desiredPos.set(
    0,
    ship.mesh.position.y + camHeight,
    ship.mesh.position.z + camBack
  );

  const lookAhead = 100.0;
  // Look at the horizon center, not the ship's specific X, to keep the lane straight
  _lookAt.set(0, ship.mesh.position.y, ship.mesh.position.z - lookAhead);

  // Smooth follow
  const follow = 1.0 - Math.pow(0.001, dt);

  // Apply
  camera.position.lerp(_desiredPos, follow);
  camera.lookAt(_lookAt);
}