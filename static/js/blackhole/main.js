import { initThree } from "./three/three_boot.js";
import { createGrid, followGridToShip } from "./three/grid.js";
import { createShip } from "./three/ship.js";
import { Universe } from "./three/universe.js";
import { checkCollision } from "./three/asteroids.js";
import { updateShip } from "./input/ship_controls.js";
import { initOverlay } from "./phaser/phaser_overlay.js";
import { setupResize } from "./shared/resize.js";
import { updateChaseCamera } from "./input/camera_controls.js";
import { input } from "./input/input_state.js";
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

function createToolbox(config) {
    const container = document.getElementById("toolbox-content");
    if (!container) return;
    container.innerHTML = "";
    function walk(obj, path = []) {
        for (const key in obj) {
            const val = obj[key];
            const currentPath = [...path, key];
            if (typeof val === 'object' && val !== null && !Array.isArray(val)) {
                const group = document.createElement("div");
                group.className = "control-group";
                group.innerHTML = `<h3>${key}</h3>`;
                container.appendChild(group);
                walk(val, currentPath);
            }
            else if (typeof val === 'number') {
                const row = document.createElement("div");
                row.className = "slider-row";
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
                    obj[key] = v;
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

async function boot() {
  console.log("[BOOT] Fetching tuning...");

  let config = {
      ship: {
          baseSpeed: 70,
          boostSpeed: 120,
          brakePower: 80,
          hoverOffset: 12.0,
          maxLateralSpeed: 550,
          lateralAccel: 25.0,
          lateralFriction: 8.0,
          boxWidth: 520,
          boundaryEdge: 510,
          boundaryStrength: 40.0
      },
      universe: { sectorSize: 300, voidChance: 0.1 },
      // [SYNC] Marble Physics Defaults
      grid: { softening: 5.0, depth: 80.0, scale: 0.35 },
      planets: { minCount: 1, maxCount: 2, radiusMin: 12, radiusMax: 25, massMultiplier: 0.3 },
      blackholes: { chance: 0.08, radiusMin: 20, radiusMax: 35, massMultiplier: 1.5 },
      asteroids: { minSectorAsteroids: 3, maxSectorAsteroids: 8 }
  };

  try {
      const configRes = await fetch("/api/tuning");
      if(configRes.ok) config = await configRes.json();
  } catch(e) { console.warn("Using default tuning"); }

  createToolbox(config);

  window.addEventListener("keydown", (e) => {
      if (e.key === '1') {
          const box = document.getElementById("toolbox");
          if (box) box.style.display = box.style.display === "block" ? "none" : "block";
      }
      if (e.key === 'Enter' && isGameOver) {
          window.location.reload();
      }
  });

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

  if(config.ship.boxWidth) ship.state.boxWidth = config.ship.boxWidth;

  const phaserGame = initOverlay(ship);
  setupResize(renderer, camera, phaserGame);

  let last = performance.now();
  let isGameOver = false;
  const _tempV = new THREE.Vector3();

  function loop(t) {
    if (isGameOver) return;
    const dt = Math.min(0.033, (t - last) / 1000);
    last = t;

    if(config.ship.boxWidth) ship.state.boxWidth = config.ship.boxWidth;

    if (config.grid) {
        if (config.grid.softening !== undefined) uniforms.uSoftening.value = config.grid.softening;
        if (config.grid.depth !== undefined) uniforms.uDepth.value = config.grid.depth;
        if (config.grid.scale !== undefined) uniforms.uGridScale.value = config.grid.scale;
    }

    uniforms.uTime.value += dt;
    const globalTime = uniforms.uTime.value;

    updateShip(ship, camera, renderer, dt, globalTime, universe.activePlanets, config.ship);
    updateChaseCamera(camera, ship, dt);
    followGridToShip(gridMesh, ship.mesh);
    universe.update(ship.mesh, dt, globalTime);

    if (phaserGame && phaserGame.updateShipVisuals) {
        ship.mesh.getWorldPosition(_tempV);
        _tempV.project(camera);

        const x = (_tempV.x * .5 + .5) * canvas.clientWidth;
        const y = (_tempV.y * -.5 + .5) * canvas.clientHeight;
        const isBurnerOn = input.keys.has("ArrowUp");

        phaserGame.updateShipVisuals(x, y, isBurnerOn);
    }

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
      const pRadius = p.userData.r || p.geometry.parameters.radius;
      const r = (pRadius * 1.5) + shipR;
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