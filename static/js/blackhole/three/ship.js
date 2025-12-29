import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

export function createShip(scene) {
  const mesh = new THREE.Mesh(
    new THREE.ConeGeometry(0.65, 1.6, 4, 1),
    new THREE.MeshStandardMaterial({ color: 0xffffff })
  );

  // Rotate to point forward (-Z)
  mesh.rotation.y = Math.PI / 4;
  mesh.position.set(0, 3, 0);

  scene.add(mesh);

  return {
    mesh,
    radius: 0.55,
    state: {
      y: 3,
      speedPx: 140, // Reduced from 280 for slower movement
      boxWidth: 360,
      boxHeight: 210,
      boxBottom: 70
    }
  };
}