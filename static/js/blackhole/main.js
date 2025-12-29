// ... existing imports
import { initThree } from "./three/three_boot.js";
import { createGrid, followGridToShip } from "./three/grid.js";
import { createShip } from "./three/ship.js";
import { Universe } from "./three/universe.js";
import { spawnAsteroids, updateAsteroids, checkShipCollision } from "./three/asteroids.js";
import { updateShip } from "./input/ship_controls.js"; // Updated import logic
import { initOverlay } from "./phaser/phaser_overlay.js";
import { setupResize } from "./shared/resize.js";
import { updateChaseCamera } from "./input/camera_controls.js";
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

// ... [Setup code remains same] ...
const canvas = document.getElementById("threeCanvas");
const { renderer, scene, camera } = initThree(canvas);
window.__camera = camera;

const { mesh: gridMesh, uniforms } = createGrid(scene);
const ship = createShip(scene);
const universe = new Universe(scene, uniforms);

const dummyPlanet = {
  mesh: { position: new THREE.Vector3(), geometry: { parameters: { radius: 2 }}}
};
const asteroidPool = spawnAsteroids(scene, [dummyPlanet, dummyPlanet, dummyPlanet], ship.state.y);

const phaserGame = initOverlay(ship);
setupResize(renderer, camera, phaserGame);

let last = performance.now();
let isGameOver = false;

function loop(t) {
  if (isGameOver) return;

  const dt = Math.min(0.033, (t - last) / 1000);
  last = t;
  uniforms.uTime.value += dt;

  // --- CHANGED: Pass activePlanets to ship for height calculation ---
  updateShip(ship, camera, renderer, dt, universe.activePlanets);

  updateChaseCamera(camera, ship, dt);
  followGridToShip(gridMesh, ship.mesh);
  universe.update(ship.mesh);

  if (universe.activePlanets && universe.activePlanets.length > 0) {
    asteroidPool.forEach((a, i) => {
        const p = universe.activePlanets[i % universe.activePlanets.length];
        const dx = a.mesh.position.x - p.position.x;
        const dz = a.mesh.position.z - p.position.z;
        if (dx*dx + dz*dz > 50000) {
             a.angle = Math.random() * Math.PI * 2;
        }
        a.planet = { mesh: p };
        a.orbit = p.userData.r + 3.0 + (i % 3);
    });
  }
  updateAsteroids(asteroidPool, dt);

  // Checks
  if (checkShipCollision(ship, asteroidPool)) {
    triggerGameOver("Hull Critical: Asteroid Impact");
    return;
  }
  if (checkPlanetCollision(ship, universe.activePlanets)) {
    triggerGameOver("Atmospheric Entry Failed: Planet Collision");
    return;
  }

  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}

function checkPlanetCollision(ship, planets) {
  const shipPos = ship.mesh.position;
  const shipR = ship.radius * 0.8;
  for (const p of planets) {
    const distSq = shipPos.distanceToSquared(p.position);
    const r = p.geometry.parameters.radius + shipR;
    if (distSq < r * r) return true;
  }
  return false;
}

function triggerGameOver(reason) {
  console.log("[GAME OVER]", reason);
  isGameOver = true;
  if (phaserGame && phaserGame.showGameOver) {
    phaserGame.showGameOver(reason);
  }
}

requestAnimationFrame(loop);
console.log("[BOOT] main loop started");