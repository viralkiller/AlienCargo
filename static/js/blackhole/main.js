import { initThree } from "./three/three_boot.js";
import { createGrid, followGridToShip } from "./three/grid.js";
import { createShip } from "./three/ship.js";
import { Universe } from "./three/universe.js";
import { spawnAsteroids, updateAsteroids, checkShipCollision } from "./three/asteroids.js";
import { updateShip } from "./input/ship_controls.js";
import { initOverlay } from "./phaser/phaser_overlay.js";
import { setupResize } from "./shared/resize.js";
import { updateChaseCamera } from "./input/camera_controls.js";
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

const canvas = document.getElementById("threeCanvas");
const { renderer, scene, camera } = initThree(canvas);
window.__camera = camera;

const { mesh: gridMesh, uniforms } = createGrid(scene);
const ship = createShip(scene);

// Initialize the Infinite Universe Manager
const universe = new Universe(scene, uniforms);

// Create a pool of asteroids.
// We pass a dummy list of planets initially because the Universe loads async.
// This ensures the asteroid meshes are created. We will re-bind them in the loop.
const dummyPlanet = {
    mesh: { position: new THREE.Vector3(), geometry: { parameters: { radius: 2 }}}
};
// Spawn 3 groups of asteroids based on dummy data to fill the pool
const asteroidPool = spawnAsteroids(scene, [dummyPlanet, dummyPlanet, dummyPlanet], ship.state.y);

const phaserGame = initOverlay(ship);
setupResize(renderer, camera, phaserGame);

let last = performance.now();

function loop(t) {
  const dt = Math.min(0.033, (t - last) / 1000);
  last = t;

  uniforms.uTime.value += dt;

  // Ship moves in its bottom box
  updateShip(ship, camera, renderer, dt);

  // Camera is locked to ship (chase)
  updateChaseCamera(camera, ship, dt);

  // Keep grid under ship (no edges, constant memory)
  followGridToShip(gridMesh, ship.mesh);

  // Universe Logic (Handles loading/unloading/rendering planets)
  universe.update(ship.mesh);

  // Asteroid Logic: Bind asteroids to currently active planets
  // This allows asteroids to reuse the pool and appear around whatever is close
  if (universe.activePlanets && universe.activePlanets.length > 0) {
    asteroidPool.forEach((a, i) => {
        // Distribute asteroids among the visible planets
        const p = universe.activePlanets[i % universe.activePlanets.length];

        // If the asteroid is extremely far from its assigned planet (e.g. planet unloaded),
        // snap it back to the new planet immediately
        const dx = a.mesh.position.x - p.position.x;
        const dz = a.mesh.position.z - p.position.z;
        if (dx*dx + dz*dz > 50000) {
             a.angle = Math.random() * Math.PI * 2; // Reset orbit angle
        }

        // Update the reference so updateAsteroids() calculates orbit around THIS planet
        a.planet = { mesh: p };
        // Update orbit radius based on the new planet's size
        a.orbit = p.userData.r + 3.0 + (i % 3);
    });
  }

  updateAsteroids(asteroidPool, dt);

  if (checkShipCollision(ship, asteroidPool)) {
    console.log("[COLLISION] ship hit asteroid");
  }

  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}

requestAnimationFrame(loop);
console.log("[BOOT] main loop started");