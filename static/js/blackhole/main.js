import { initThree } from "./three/three_boot.js";
import { createGrid, followGridToShip } from "./three/grid.js";
import { createShip } from "./three/ship.js";
import { Universe } from "./three/universe.js";
import { checkShipCollision } from "./three/asteroids.js"; // Note: Only collision check here now
import { updateShip } from "./input/ship_controls.js";
import { initOverlay } from "./phaser/phaser_overlay.js";
import { setupResize } from "./shared/resize.js";
import { updateChaseCamera } from "./input/camera_controls.js";
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

async function boot() {
  console.log("[BOOT] Fetching tuning...");
  const configRes = await fetch("/api/tuning");
  const config = await configRes.json();
  console.log("[BOOT] Tuning loaded:", config);

  const canvas = document.getElementById("threeCanvas");
  const { renderer, scene, camera } = initThree(canvas);
  window.__camera = camera;

  // Pass config to Grid
  const { mesh: gridMesh, uniforms } = createGrid(scene, config.grid);
  const ship = createShip(scene);

  // Initialize Universe with config
  const universe = new Universe(scene, uniforms, config);

  // Note: We removed the "Asteroid Pool". Asteroids are now managed inside the Universe/Planets.

  const phaserGame = initOverlay(ship);
  setupResize(renderer, camera, phaserGame);

  let last = performance.now();
  let isGameOver = false;

  function loop(t) {
    if (isGameOver) return;

    const dt = Math.min(0.033, (t - last) / 1000);
    last = t;
    uniforms.uTime.value += dt;

    // Pass config to Ship
    updateShip(ship, camera, renderer, dt, universe.activePlanets, config.ship);

    updateChaseCamera(camera, ship, dt);
    followGridToShip(gridMesh, ship.mesh);

    // Universe handles planets AND their child asteroids now
    universe.update(ship.mesh, dt);

    // Collision Checks need to look at all active planets' children
    // We gather all asteroids from active planets for collision
    const allAsteroids = [];
    universe.activePlanets.forEach(p => {
        if (p.userData.asteroids) {
            allAsteroids.push(...p.userData.asteroids);
        }
    });

    if (checkShipCollision(ship, allAsteroids)) {
      triggerGameOver("Hull Critical: Asteroid Impact");
      return;
    }

    // Check Planet Collision
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
}

boot();