// static/js/blackhole/three/asteroids.js
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { rand } from "../shared/math.js";

function ruggedizeGeometry(geometry, amount) {
  const posAttribute = geometry.attributes.position;
  const vertex = new THREE.Vector3();
  for (let i = 0; i < posAttribute.count; i++) {
    vertex.fromBufferAttribute(posAttribute, i);
    const deform = 1.0 + (Math.random() - 0.5) * amount;
    vertex.multiplyScalar(deform);
    posAttribute.setXYZ(i, vertex.x, vertex.y, vertex.z);
  }
  geometry.computeVertexNormals();
  return geometry;
}

export function createFreeAsteroid(data) {
  const r = data.r || rand(0.5, 1.5);

  const geo = new THREE.DodecahedronGeometry(r, 0); // Low poly look
  ruggedizeGeometry(geo, 0.4);

  const mat = new THREE.MeshStandardMaterial({
    color: 0x886655, // Brownish rock
    roughness: 0.9,
    flatShading: true
  });

  const mesh = new THREE.Mesh(geo, mat);
  mesh.position.set(data.x, data.y, data.z);

  // Velocity: Moving -Z (down screen) towards ship
  const velocity = new THREE.Vector3(
    rand(-5, 5), // Slight drift
    0,
    -rand(40, 80) // Fast downward speed
  );

  return {
    mesh,
    r: r,
    velocity: velocity,
    rotAxis: new THREE.Vector3(Math.random(), Math.random(), Math.random()).normalize(),
    rotSpeed: rand(1, 4)
  };
}

export function updateFreeAsteroids(universe, dt) {
  // We iterate through all sector meshes to find asteroids
  // This is slightly inefficient but safe for low object counts
  for (const meshes of universe.sectorMeshes.values()) {
    meshes.forEach(obj => {
      if (obj.userData.type === 'asteroid') {
        const d = obj.userData.physics;

        // Move Physics
        obj.position.addScaledVector(d.velocity, dt);
        obj.rotation.x += d.rotAxis.x * d.rotSpeed * dt;
        obj.rotation.y += d.rotAxis.y * d.rotSpeed * dt;

        // Sync visual mesh if wrapped
        // (Not strictly needed if obj IS the mesh, which it is here)
      }
    });
  }
}

export function checkCollision(ship, objectList) {
    const shipPos = ship.mesh.position;
    const worldPos = new THREE.Vector3();
    const shipR = ship.radius;

    for (const obj of objectList) {
        // Handle both Moons (children of planets) and Free Asteroids (direct meshes)
        const mesh = obj.mesh || obj;
        const r = obj.r || (mesh.geometry.parameters.radius || 1.0);

        mesh.getWorldPosition(worldPos);

        // Height check optimization
        if (Math.abs(worldPos.y - shipPos.y) > 3.5) continue;

        const dx = worldPos.x - shipPos.x;
        const dz = worldPos.z - shipPos.z;
        const distSq = dx*dx + dz*dz;

        const minDist = shipR + r;
        if (distSq < minDist * minDist) {
            return true;
        }
    }
    return false;
}