import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { rand } from "../shared/math.js";

export function spawnAsteroids(scene, planets, shipY) {
  const asteroids = [];

  planets.forEach((p) => {
    if (p.isBlackHole) return;

    const count = Math.floor(rand(4, 7));
    for (let i = 0; i < count; i++) {
      const r = rand(0.12, 0.28);
      const orbit = p.mesh.geometry.parameters.radius + rand(1.2, 3.6);

      const mesh = new THREE.Mesh(
        new THREE.SphereGeometry(r, 12, 10),
        new THREE.MeshStandardMaterial({ color: 0xaaaaaa, roughness: 0.9, metalness: 0.0 })
      );
      scene.add(mesh);

      asteroids.push({
        mesh,
        planet: p,
        angle: rand(0, Math.PI * 2),
        speed: rand(0.6, 1.8) * (Math.random() < 0.5 ? -1 : 1),
        orbit,
        r,
        y: shipY + rand(-0.2, 0.2),
      });
    }
  });

  console.log("[ASTEROIDS] spawned:", asteroids.length);
  return asteroids;
}

export function updateAsteroids(asteroids, dt) {
  asteroids.forEach((a) => {
    a.angle += a.speed * dt;
    a.mesh.position.set(
      a.planet.mesh.position.x + Math.cos(a.angle) * a.orbit,
      a.y,
      a.planet.mesh.position.z + Math.sin(a.angle) * a.orbit
    );
  });
}

export function checkShipCollision(ship, asteroids) {
  for (const a of asteroids) {
    const dx = a.mesh.position.x - ship.mesh.position.x;
    const dz = a.mesh.position.z - ship.mesh.position.z;
    const rr = (ship.radius + a.r) * (ship.radius + a.r);
    if (dx * dx + dz * dz < rr) return true;
  }
  return false;
}
