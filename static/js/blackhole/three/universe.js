import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { createPlanetMesh } from "./planets.js";
import { rand } from "../shared/math.js";
import { createAsteroidSystem, updateAsteroids } from "./asteroids.js";

const MAX_SHADER_PLANETS = 8;

export class Universe {
  constructor(scene, uniforms, config) {
    this.scene = scene;
    this.uniforms = uniforms;
    this.config = config; // Tuning data

    this.sectorData = new Map();
    this.sectorMeshes = new Map();
    this.pendingKeys = new Set();
    this.currentSector = { x: 999999, z: 999999 };
    this.shipPos = new THREE.Vector3();
    this.activePlanets = [];
  }

  update(shipMesh, dt) {
    this.shipPos.copy(shipMesh.position);
    const sx = Math.floor(shipMesh.position.x / this.config.universe.sectorSize);
    const sz = Math.floor(shipMesh.position.z / this.config.universe.sectorSize);

    if (sx !== this.currentSector.x || sz !== this.currentSector.z) {
      this.currentSector = { x: sx, z: sz };
      this.handleSectorChange(sx, sz);
    }

    // Update Asteroids on active planets
    this.activePlanets.forEach(p => {
        updateAsteroids(p, dt);
    });

    this.updateShaderGravity();
  }

  async handleSectorChange(cx, cz) {
    const keysNeeded = [];
    for (let x = cx - 1; x <= cx + 1; x++) {
      for (let z = cz - 1; z <= cz + 1; z++) {
        keysNeeded.push(`${x}:${z}`);
      }
    }

    for (const [key, meshes] of this.sectorMeshes) {
      if (!keysNeeded.includes(key)) {
        meshes.forEach(m => {
            this.scene.remove(m);
            if(m.geometry) m.geometry.dispose();
            if(m.material) m.material.dispose();
            // Cleanup child asteroids is automatic in Scene,
            // but we drop references in memory
            m.userData.asteroids = null;
        });
        this.sectorMeshes.delete(key);
      }
    }

    const keysToFetch = keysNeeded.filter(k => !this.sectorData.has(k) && !this.pendingKeys.has(k));
    if (keysToFetch.length > 0) {
      await this.fetchSectors(keysToFetch);
    }

    keysNeeded.forEach(key => {
      if (this.sectorData.has(key) && !this.sectorMeshes.has(key)) {
        this.buildSector(key);
      }
    });
  }

  async fetchSectors(keys) {
    keys.forEach(k => this.pendingKeys.add(k));
    try {
      const params = new URLSearchParams({ keys: keys.join(",") });
      const res = await fetch(`/api/universe/load?${params}`);
      const data = await res.json();

      const newSectors = {};
      let hasNewData = false;

      keys.forEach(key => {
        if (data[key]) {
          this.sectorData.set(key, data[key]);
        } else {
          const generated = this.generateSector(key);
          this.sectorData.set(key, generated);
          newSectors[key] = generated;
          hasNewData = true;
        }
        this.pendingKeys.delete(key);
      });

      if (hasNewData) {
        fetch("/api/universe/save", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(newSectors)
        }).catch(e => console.error("Save failed", e));
      }
    } catch (e) {
      console.error("Universe fetch error:", e);
      keys.forEach(k => this.pendingKeys.delete(k));
    }
  }

  generateSector(key) {
    const uConf = this.config.universe;
    const [sx, sz] = key.split(":").map(Number);
    const planets = [];

    if (sx === 0 && sz === 0) return []; // Start safe zone
    if (Math.random() < uConf.voidChance) return [];

    const count = Math.floor(rand(1, uConf.maxPlanetsPerSector));

    for (let i = 0; i < count; i++) {
      const isBlackHole = Math.random() < uConf.blackHoleChance;

      const r = isBlackHole
        ? rand(uConf.blackHoleScaleMin, uConf.blackHoleScaleMax)
        : rand(uConf.planetScaleMin, uConf.planetScaleMax);

      const lx = rand(-uConf.sectorSize * 0.4, uConf.sectorSize * 0.4);
      const lz = rand(-uConf.sectorSize * 0.4, uConf.sectorSize * 0.4);

      const mass = isBlackHole
        ? r * r * uConf.blackHoleMassMultiplier
        : r * uConf.planetMassMultiplier;

      planets.push({
        x: sx * uConf.sectorSize + lx,
        y: rand(0, 10),
        z: sz * uConf.sectorSize + lz,
        r: r,
        mass: mass,
        type: isBlackHole ? "blackhole" : "planet",
        colorHue: Math.random()
      });
    }
    return planets;
  }

  buildSector(key) {
    const data = this.sectorData.get(key);
    const meshes = [];
    data.forEach(pData => {
      const mesh = createPlanetMesh(pData);
      mesh.position.set(pData.x, pData.y, pData.z);

      // CREATE ASTEROID SYSTEM
      if (!pData.isBlackHole) {
        const asteroids = createAsteroidSystem(mesh, this.config.asteroids);
        // Link asteroids to planet for updates
        mesh.userData.asteroids = asteroids;
      }

      this.scene.add(mesh);
      mesh.userData = { ...mesh.userData, ...pData };
      meshes.push(mesh);
    });
    this.sectorMeshes.set(key, meshes);
  }

  updateShaderGravity() {
    let allMeshes = [];
    for (const meshes of this.sectorMeshes.values()) {
      allMeshes = allMeshes.concat(meshes);
    }

    allMeshes.sort((a, b) => {
      const d1 = a.position.distanceToSquared(this.shipPos);
      const d2 = b.position.distanceToSquared(this.shipPos);
      return d1 - d2;
    });

    const closest = allMeshes.slice(0, MAX_SHADER_PLANETS);
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