import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { makeGridMaterial } from "./grid_shader.js";

export function createGrid(scene) {
  const { material, uniforms } = makeGridMaterial(THREE);

  // Moderate size plane: constant memory.
  // Pattern is infinite due to world-based shader.
  const geo = new THREE.PlaneGeometry(180, 180, 240, 240);
  geo.rotateX(-Math.PI / 2);

  const mesh = new THREE.Mesh(geo, material);
  mesh.position.set(0, 0, 0);
  scene.add(mesh);

  return { mesh, uniforms };
}

export function followGridToShip(gridMesh, shipMesh) {
  // Keep grid centered under ship to avoid seeing edges
  gridMesh.position.x = shipMesh.position.x;
  gridMesh.position.z = shipMesh.position.z;
}
