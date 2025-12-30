import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { createPlanetMesh } from "./planets.js";
import { rand } from "../shared/math.js";
import { createMoonSystem, updateMoons } from "./moons.js";
import { createFreeAsteroid, updateFreeAsteroids } from "./asteroids.js";

const MAX_SHADER_PLANETS = 8;

export class Universe {
  constructor(scene, uniforms, config) {
    this.scene = scene;
    this.uniforms = uniforms;
    this.config = config;
    this.sectorData = new Map();
    this.sectorMeshes = new Map();
    this.pendingKeys = new Set();
    this.currentRowZ = -999999;
    this.shipPos = new THREE.Vector3();
    this.activePlanets = [];
    this.freeAsteroids = [];
  }

  update(shipMesh, dt, time) {
    this.shipPos.copy(shipMesh.position);

    // Update Sector Logic
    const sz = Math.floor(shipMesh.position.z / this.config.universe.sectorSize);
    if (sz !== this.currentRowZ) {
      this.currentRowZ = sz;
      this.updateCorridor(sz);
    }

    // Update Moons
    this.activePlanets.forEach(p => {
        updateMoons(p, dt);
    });

    // Update Free Asteroids
    updateFreeAsteroids(this, dt);

    this.updateShaderGravity();
  }

  async updateCorridor(currentZ) {
    const keysNeeded = [];
    const forwardView = 2;
    for (let z = currentZ; z <= currentZ + forwardView; z++) {
        for (let x = -1; x <= 1; x++) {
            keysNeeded.push(`${x}:${z}`);
        }
    }

    // Cleanup
    for (const [key, meshes] of this.sectorMeshes) {
      if (!keysNeeded.includes(key)) {
        meshes.forEach(m => {
            this.scene.remove(m);
            if(m.geometry) m.geometry.dispose();
            if(m.material) m.material.dispose();
            if(m.userData.moons) {
                m.userData.moons.forEach(moon => {
                    m.remove(moon.mesh);
                    moon.mesh.geometry.dispose();
                    moon.mesh.material.dispose();
                });
            }
        });
        this.sectorMeshes.delete(key);
      }
    }

    // Fetch/Gen
    const keysToFetch = keysNeeded.filter(k => !this.sectorData.has(k) && !this.pendingKeys.has(k));
    if (keysToFetch.length > 0) {
      await this.fetchSectors(keysToFetch);
    }

    // Build
    keysNeeded.forEach(key => {
      if (this.sectorData.has(key) && !this.sectorMeshes.has(key)) {
        this.buildSector(key);
      }
    });
  }

  async fetchSectors(keys) {
    keys.forEach(k => this.pendingKeys.add(k));
    keys.forEach(key => {
        if (!this.sectorData.has(key)) {
            const generated = this.generateSector(key);
            this.sectorData.set(key, generated);
        }
        this.pendingKeys.delete(key);
    });
  }

  generateSector(key) {
    const uConf = this.config.universe;
    const pConf = this.config.planets;
    const bConf = this.config.blackholes;
    const aConf = this.config.asteroids;

    const [sx, sz] = key.split(":").map(Number);

    // Safe Zone
    if (sx === 0 && sz === 0) return [];
    if (Math.random() < uConf.voidChance) return [];

    const objects = [];

    // 1. Planets / Blackholes
    const count = Math.floor(rand(pConf.minCount, pConf.maxCount));

    for (let i = 0; i < count; i++) {
      const isBlackHole = Math.random() < bConf.chance;

      let r;
      if (isBlackHole) {
          r = rand(bConf.radiusMin, bConf.radiusMax);
      } else {
          r = rand(pConf.radiusMin, pConf.radiusMax);
      }

      // [FIX] Calculate Float Height
      // Planets float above the grid (y=0).
      // We set y = radius + small_gap so they sit "on top" of the warp.
      const floatHeight = r + 2.0;

      const massScale = isBlackHole ? bConf.massMultiplier : pConf.massMultiplier;
      const mass = isBlackHole ? (r * r * massScale) : (r * massScale);

      const lx = (Math.random() * uConf.sectorSize) - (uConf.sectorSize/2);
      const lz = (Math.random() * uConf.sectorSize) - (uConf.sectorSize/2);

      objects.push({
        x: sx * uConf.sectorSize + lx,
        y: floatHeight, // [FIX] Applied here
        z: sz * uConf.sectorSize + lz,
        r: r,
        mass: mass,
        type: isBlackHole ? "blackhole" : "planet",
        colorHue: Math.random()
      });
    }

    // 2. Free Floating Asteroids
    const asteroidCount = Math.floor(rand(aConf.minSectorAsteroids, aConf.maxSectorAsteroids));
    for(let j=0; j<asteroidCount; j++) {
        const lx = (Math.random() * uConf.sectorSize) - (uConf.sectorSize/2);
        const lz = (Math.random() * uConf.sectorSize) - (uConf.sectorSize/2);
        objects.push({
            x: sx * uConf.sectorSize + lx,
            y: rand(4, 10), // Raised slightly to match new planet heights
            z: sz * uConf.sectorSize + lz,
            r: rand(0.5, 1.2),
            type: "asteroid"
        });
    }

    return objects;
  }

  buildSector(key) {
    const data = this.sectorData.get(key);
    const meshes = [];

    data.forEach(pData => {
      if (pData.type === 'asteroid') {
          const physData = createFreeAsteroid(pData);
          const mesh = physData.mesh;
          mesh.userData = { ...pData, physics: physData };
          this.scene.add(mesh);
          meshes.push(mesh);
      } else {
          const mesh = createPlanetMesh(pData);
          mesh.position.set(pData.x, pData.y, pData.z);

          if (pData.type !== 'blackhole') {
            const moons = createMoonSystem(mesh, this.config.moons);
            mesh.userData.moons = moons;
          }

          this.scene.add(mesh);
          mesh.userData = { ...mesh.userData, ...pData };
          meshes.push(mesh);
      }
    });

    this.sectorMeshes.set(key, meshes);
  }

  updateShaderGravity() {
    let allPlanets = [];
    for (const meshes of this.sectorMeshes.values()) {
        meshes.forEach(m => {
            if (m.userData.type === 'planet' || m.userData.type === 'blackhole') {
                allPlanets.push(m);
            }
        });
    }

    allPlanets.sort((a, b) => a.position.distanceToSquared(this.shipPos) - b.position.distanceToSquared(this.shipPos));
    const closest = allPlanets.slice(0, MAX_SHADER_PLANETS);

    this.activePlanets = closest;
    this.uniforms.uPlanetCount.value = closest.length;

    for (let i = 0; i < MAX_SHADER_PLANETS; i++) {
      if (i < closest.length) {
        this.uniforms.uPlanetPos.value[i].copy(closest[i].position);
        this.uniforms.uPlanetMass.value[i] = closest[i].userData.mass;
      } else {
        this.uniforms.uPlanetPos.value[i].set(99999, 99999, 99999);
        this.uniforms.uPlanetMass.value[i] = 0;
      }
    }
  }
}