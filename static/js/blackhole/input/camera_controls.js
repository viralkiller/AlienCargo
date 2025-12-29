import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

const _desiredPos = new THREE.Vector3();
const _lookAt = new THREE.Vector3();
const _forward = new THREE.Vector3(0, 0, -1);

export function updateChaseCamera(camera, ship, dt) {
  // Ship forward from its yaw
  const shipYaw = ship.mesh.rotation.y - Math.PI / 4;
  const shipForward = _forward.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), shipYaw);

  // Camera offset behind/above ship in WORLD space
  // [TUNING] Pulled back and up for a wider view
  const camHeight = 18.0; // Was 13.5
  const camBack = 35.0;   // Was 27.5

  _desiredPos.set(
    ship.mesh.position.x,
    ship.mesh.position.y + camHeight,
    ship.mesh.position.z + camBack
  );

  const lookAhead = 100.0;
  _lookAt.copy(ship.mesh.position).addScaledVector(shipForward, lookAhead);

  // Smooth follow
  const follow = 1.0 - Math.pow(0.001, dt);
  camera.position.lerp(_desiredPos, follow);
  camera.lookAt(_lookAt);
}