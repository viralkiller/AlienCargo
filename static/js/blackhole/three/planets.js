import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { rand } from "../shared/math.js";

export function spawnPlanets(scene, uniforms) {
  const planets = [];

  const anchors = [
    [-35, 22],
    [22, 20],
    [-18, -18],
    [0, 0],
    [36, -20],
    [-38, -26],
    [10, 30],
  ];

  anchors.forEach(([x, z], i) => {
    const isBlackHole = i === 3;
    const r = isBlackHole ? rand(1.3, 2.0) : rand(0.9, 2.4);
    const mass = r * r * (isBlackHole ? 18 : 3);

    const mesh = new THREE.Mesh(
      new THREE.SphereGeometry(r, 24, 18),
      new THREE.MeshStandardMaterial({
        color: isBlackHole ? 0x050508 : new THREE.Color().setHSL(Math.random(), 0.6, 0.55),
        roughness: isBlackHole ? 0.25 : 0.55,
        metalness: 0.0,
      })
    );

    mesh.position.set(x + rand(-2, 2), rand(3, 6), z + rand(-2, 2));
    scene.add(mesh);

    planets.push({ mesh, mass, isBlackHole });
  });

  uniforms.uPlanetCount.value = planets.length;
  planets.forEach((p, i) => {
    uniforms.uPlanetPos.value[i].copy(p.mesh.position);
    uniforms.uPlanetMass.value[i] = p.mass;
  });

  return planets;
}
