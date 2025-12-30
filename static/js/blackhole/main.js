import { initThree } from "./three/three_boot.js";
import { createGrid, followGridToShip } from "./three/grid.js";
import { createShip } from "./three/ship.js";
import { Universe } from "./three/universe.js";
import { checkCollision } from "./three/asteroids.js";
import { updateShip } from "./input/ship_controls.js";
import { initOverlay } from "./phaser/phaser_overlay.js";
import { setupResize } from "./shared/resize.js";
import { updateChaseCamera } from "./input/camera_controls.js";
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

// --- TOOLBOX GENERATOR ---
function createToolbox(config) {
    const container = document.getElementById("toolbox-content");

    // [SAFETY CHECK] Prevent crash if index.html is not updated
    if (!container) {
        console.warn("Toolbox container (#toolbox-content) not found in HTML. UI skipped.");
        return;
    }

    container.innerHTML = "";

    // Recursive function to walk the JSON and make sliders
    function walk(obj, path = []) {
        for (const key in obj) {
            const val = obj[key];
            const currentPath = [...path, key];

            if (typeof val === 'object' && val !== null && !Array.isArray(val)) {
                // It's a folder/category
                const group = document.createElement("div");
                group.className = "control-group";
                group.innerHTML = `<h3>${key}</h3>`;
                container.appendChild(group);
                walk(val, currentPath);
            }
            else if (typeof val === 'number') {
                // It's a number -> Make a slider
                const row = document.createElement("div");
                row.className = "slider-row";

                // Determine ranges
                let min = 0;
                let max = val > 1 ? val * 4 : 2;
                let step = val % 1 !== 0 || val < 5 ? 0.01 : 1;
                if (val === 0) max = 100;

                const label = document.createElement("div");
                label.className = "slider-label";
                label.innerHTML = `<span>${key}</span><span id="disp-${currentPath.join('-')}">${val.toFixed(2)}</span>`;

                const input = document.createElement("input");
                input.type = "range";
                input.min = min;
                input.max = max;
                input.step = step;
                input.value = val;

                input.oninput = (e) => {
                    const v = parseFloat(e.target.value);
                    obj[key] = v; // Update the live config object
                    const disp = document.getElementById(`disp-${currentPath.join('-')}`);
                    if(disp) disp.innerText = v.toFixed(2);
                };

                row.appendChild(label);
                row.appendChild(input);
                container.appendChild(row);
            }
        }
    }
    walk(config);
}

// --- MAIN BOOT ---
async function boot() {
  console.log("[BOOT] Fetching tuning...");

  // Default fallback
  let config = {
      ship: {
          baseSpeed: 50,
          maxLateralSpeed: 300,
          lateralAccel: 15.0,
          lateralFriction: 8.0,
          hoverOffset: 4.0,
          brakePower: 80,
          boxWidth: 360,
          boundaryEdge: 350
      },
      universe: {
          sectorSize: 300,
          maxPlanetsPerSector: 2,
          blackHoleChance: 0.1,
          voidChance: 0.1
      },
      grid: {
         softening: 8.0,
         depth: 20.0
      }
  };

  try {
      const configRes = await fetch("/api/tuning");
      if(configRes.ok) config = await configRes.json();
  } catch(e) { console.warn("Using default tuning"); }

  // 1. Setup Toolbox
  createToolbox(config);

  // 2. Toggle Toolbox with '1'
  window.addEventListener("keydown", (e) => {
      if (e.key === '1') {
          const box = document.getElementById("toolbox");
          if (box) {
             box.style.display = box.style.display === "block" ? "none" : "block";
          }
      }
  });

  // 3. Save Button Log
  const saveBtn = document.getElementById("saveBtn");
  if (saveBtn) {
      saveBtn.onclick = () => {
          console.log(JSON.stringify(config, null, 2));
          alert("Config logged to console (F12)");
      };
  }

  const canvas = document.getElementById("threeCanvas");
  const { renderer, scene, camera } = initThree(canvas);
  window.__camera = camera;

  const { mesh: gridMesh, uniforms } = createGrid(scene, config.grid);
  const ship = createShip(scene);
  const universe = new Universe(scene, uniforms, config);

  // Sync ship box size with config if present
  if(config.ship.boxWidth) ship.state.boxWidth = config.ship.boxWidth;

  const phaserGame = initOverlay(ship);
  setupResize(renderer, camera, phaserGame);

  let last = performance.now();
  let isGameOver = false;

  function loop(t) {
    if (isGameOver) return;
    const dt = Math.min(0.033, (t - last) / 1000);
    last = t;

    // Live update box width from config sliders
    if(config.ship.boxWidth) ship.state.boxWidth = config.ship.boxWidth;

    uniforms.uTime.value += dt;
    const globalTime = uniforms.uTime.value;

    updateShip(ship, camera, renderer, dt, globalTime, universe.activePlanets, config.ship);
    updateChaseCamera(camera, ship, dt);
    followGridToShip(gridMesh, ship.mesh);

    universe.update(ship.mesh, dt, globalTime);

    // Collect threats
    const threats = [];
    universe.activePlanets.forEach(p => {
        if (p.userData.moons) threats.push(...p.userData.moons);
    });
    universe.sectorMeshes.forEach(meshes => {
        meshes.forEach(m => {
            if (m.userData.type === 'asteroid') threats.push(m.userData.physics);
        });
    });

    if (checkCollision(ship, threats)) {
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
      if (Math.abs(p.position.z - shipPos.z) > 40) continue;
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