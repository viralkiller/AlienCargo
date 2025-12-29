import { initThree } from "./three/three_boot.js";
import { createGrid, followGridToShip } from "./three/grid.js";
import { createShip } from "./three/ship.js";
import { spawnPlanets } from "./three/planets.js";
import { spawnAsteroids, updateAsteroids, checkShipCollision } from "./three/asteroids.js";
import { updateShip } from "./input/ship_controls.js";
import { initOverlay } from "./phaser/phaser_overlay.js";
import { setupResize } from "./shared/resize.js";
import { updateChaseCamera } from "./input/camera_controls.js";

const canvas = document.getElementById("threeCanvas");
const { renderer, scene, camera } = initThree(canvas);
window.__camera = camera;

const { mesh: gridMesh, uniforms } = createGrid(scene);

const ship = createShip(scene);
const planets = spawnPlanets(scene, uniforms);
const asteroids = spawnAsteroids(scene, planets, ship.state.y);

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

  // Orbiting hazards
  updateAsteroids(asteroids, dt);

  if (checkShipCollision(ship, asteroids)) {
    console.log("[COLLISION] ship hit asteroid");
  }

  renderer.render(scene, camera);
  requestAnimationFrame(loop);
}

requestAnimationFrame(loop);
console.log("[BOOT] main loop started");
