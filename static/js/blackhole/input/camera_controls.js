import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

const _desiredPos = new THREE.Vector3();
const _lookAt = new THREE.Vector3();
const _forward = new THREE.Vector3(0, 0, -1);

export function updateChaseCamera(camera, ship, dt) {
  // Ship forward from its yaw
  const shipYaw = ship.mesh.rotation.y - Math.PI / 4;
  const shipForward = _forward.clone().applyAxisAngle(new THREE.Vector3(0, 1, 0), shipYaw);

  // Camera offset behind/above ship in WORLD space
  const camHeight = 13.5;
  const camBack = 27.5;

  // Keep symmetrical: behind is +Z when ship forward is -Z
  _desiredPos.set(
    ship.mesh.position.x,
    ship.mesh.position.y + camHeight,
    ship.mesh.position.z + camBack
  );

  // Look ahead so ship sits lower
  // FIX: Increased lookAhead from 12.0 to 100.0.
  // This tilts the camera up, pushing the ship's visual position down to the
  // bottom of the screen where the control box is located.
  // This aligns the "neutral" cursor position with the ship's actual position,
  // preventing the infinite backward drift loop.
  const lookAhead = 100.0;
  _lookAt.copy(ship.mesh.position).addScaledVector(shipForward, lookAhead);

  // Smooth follow (stable + nice)
  const follow = 1.0 - Math.pow(0.001, dt); // dt-correct smoothing
  camera.position.lerp(_desiredPos, follow);
  camera.lookAt(_lookAt);

  // Debug log occasionally (not every frame)
  // You can uncomment if needed:
  // if (Math.random() < 0.01) console.log("[CAM][CHASE]", camera.position.toArray().map(n=>n.toFixed(2)).join(","));
}