import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

// Pure factory: No scene adding, just mesh creation
export function createPlanetMesh(data) {
  const isBlackHole = data.type === "blackhole";

  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(data.r, 24, 18),
    new THREE.MeshStandardMaterial({
      color: isBlackHole
        ? 0x050508
        : new THREE.Color().setHSL(data.colorHue, 0.6, 0.55),
      roughness: isBlackHole ? 0.25 : 0.55,
      metalness: 0.0,
      emissive: isBlackHole ? 0x110022 : 0x000000,
    })
  );

  return mesh;
}