import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { makeGridMaterial } from "./grid_shader.js";

export function createGrid(scene) {
  const { material, uniforms } = makeGridMaterial(THREE);

  // [FIX] Reduced detail x2 (200 -> 100 segments)
  const geo = new THREE.PlaneGeometry(800, 800, 100, 100);
  geo.rotateX(-Math.PI / 2);

  const mesh = new THREE.Mesh(geo, material);

  // [FIX] Grid at Y=-2.0 to slice the planets
  mesh.position.set(0, -2.0, 0);

  mesh.frustumCulled = false;

  scene.add(mesh);
  return { mesh, uniforms };
}

export function followGridToShip(gridMesh, shipMesh) {
  gridMesh.position.x = shipMesh.position.x;
  gridMesh.position.z = shipMesh.position.z;
}