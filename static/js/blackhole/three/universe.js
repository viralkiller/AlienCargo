// static/js/blackhole/three/universe.js
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { createPlanetMesh } from "./planets.js";
import { rand } from "../shared/math.js";

// Size of one "sector" in world units
const SECTOR_SIZE = 250;
const MAX_SHADER_PLANETS = 8;

export class Universe {
  constructor(scene, uniforms) {
    this.scene = scene;
    this.uniforms = uniforms;

    // Key: "x:z" (sector coords), Value: Array of planet data objects
    this.sectorData = new Map();

    // Key: "x:z", Value: Array of THREE.Mesh objects
    this.sectorMeshes = new Map();

    // Set of keys currently queued for fetching/saving to prevent duplicate calls
    this.pendingKeys = new Set();

    this.currentSector = { x: 999999, z: 999999 };
    this.shipPos = new THREE.Vector3();

    // Public list of planets currently in the scene (sorted by distance)
    this.activePlanets = [];
  }

  update(shipMesh) {
    this.shipPos.copy(shipMesh.position);

    // 1. Calculate current sector index based on ship position
    const sx = Math.floor(shipMesh.position.x / SECTOR_SIZE);
    const sz = Math.floor(shipMesh.position.z / SECTOR_SIZE);

    // 2. If entered new sector, manage lifecycle (load new, unload old)
    if (sx !== this.currentSector.x || sz !== this.currentSector.z) {
      this.currentSector = { x: sx, z: sz };
      this.handleSectorChange(sx, sz);
    }

    // 3. Update Shader Uniforms (pass closest 8 planets to the grid shader)
    this.updateShaderGravity();
  }

  async handleSectorChange(cx, cz) {
    // Determine the 3x3 grid of sectors around the ship to keep loaded
    const keysNeeded = [];
    for (let x = cx - 1; x <= cx + 1; x++) {
      for (let z = cz - 1; z <= cz + 1; z++) {
        keysNeeded.push(`${x}:${z}`);
      }
    }

    // 1. Unload far sectors (cleanup memory)
    for (const [key, meshes] of this.sectorMeshes) {
      if (!keysNeeded.includes(key)) {
        meshes.forEach(m => {
            this.scene.remove(m);
            if(m.geometry) m.geometry.dispose();
            if(m.material) m.material.dispose();
        });
        this.sectorMeshes.delete(key);
      }
    }

    // 2. Identify missing data
    const keysToFetch = keysNeeded.filter(k => !this.sectorData.has(k) && !this.pendingKeys.has(k));

    if (keysToFetch.length > 0) {
      await this.fetchSectors(keysToFetch);
    }

    // 3. Instantiate meshes for data we have but haven't built yet
    keysNeeded.forEach(key => {
      if (this.sectorData.has(key) && !this.sectorMeshes.has(key)) {
        this.buildSector(key);
      }
    });
  }

  async fetchSectors(keys) {
    keys.forEach(k => this.pendingKeys.add(k));

    try {
      // Ask backend for these sectors
      const params = new URLSearchParams({ keys: keys.join(",") });
      const res = await fetch(`/api/universe/load?${params}`);
      const data = await res.json();

      const newSectors = {};
      let hasNewData = false;

      keys.forEach(key => {
        if (data[key]) {
          // Found in DB
          this.sectorData.set(key, data[key]);
        } else {
          // Not found -> Procedurally Generate
          const generated = this.generateSector(key);
          this.sectorData.set(key, generated);
          newSectors[key] = generated;
          hasNewData = true;
        }
        this.pendingKeys.delete(key);
      });

      // Save newly generated sectors back to DB
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
    const [sx, sz] = key.split(":").map(Number);
    const planets = [];

    // 10% chance for an empty void sector
    const isVoid = Math.random() < 0.1;
    if (isVoid) return [];

    // 1-3 planets per sector
    const count = Math.floor(rand(1, 4));

    for (let i = 0; i < count; i++) {
      // 5% chance for a black hole
      const isBlackHole = Math.random() < 0.05;
      const r = isBlackHole ? rand(1.5, 2.5) : rand(1.0, 3.0);

      // Position relative to sector center
      const lx = rand(-SECTOR_SIZE * 0.4, SECTOR_SIZE * 0.4);
      const lz = rand(-SECTOR_SIZE * 0.4, SECTOR_SIZE * 0.4);

      planets.push({
        x: sx * SECTOR_SIZE + lx,
        y: rand(0, 10), // variable height variation
        z: sz * SECTOR_SIZE + lz,
        r: r,
        mass: r * r * (isBlackHole ? 20 : 3), // Black holes are much heavier
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
      this.scene.add(mesh);
      // Link data for logic
      mesh.userData = { ...pData };
      meshes.push(mesh);
    });
    this.sectorMeshes.set(key, meshes);
  }

  updateShaderGravity() {
    // Collect all active planets from loaded sectors
    let allMeshes = [];
    for (const meshes of this.sectorMeshes.values()) {
      allMeshes = allMeshes.concat(meshes);
    }

    // Sort by distance to ship
    allMeshes.sort((a, b) => {
      const d1 = a.position.distanceToSquared(this.shipPos);
      const d2 = b.position.distanceToSquared(this.shipPos);
      return d1 - d2;
    });

    // Pick top 8 for the shader
    const closest = allMeshes.slice(0, MAX_SHADER_PLANETS);
    this.activePlanets = closest;

    // Update Uniforms
    this.uniforms.uPlanetCount.value = closest.length;
    for (let i = 0; i < MAX_SHADER_PLANETS; i++) {
      if (i < closest.length) {
        this.uniforms.uPlanetPos.value[i].copy(closest[i].position);
        this.uniforms.uPlanetMass.value[i] = closest[i].userData.mass;
      } else {
        // Clear unused slots
        this.uniforms.uPlanetPos.value[i].set(99999, 99999, 99999);
        this.uniforms.uPlanetMass.value[i] = 0;
      }
    }
  }
}