import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { rand } from "../shared/math.js";

// Helper to noise-deform a sphere
function ruggedizeGeometry(geometry, amount) {
  const posAttribute = geometry.attributes.position;
  const vertex = new THREE.Vector3();

  for (let i = 0; i < posAttribute.count; i++) {
    vertex.fromBufferAttribute(posAttribute, i);
    // Displace along normal (which is just the normalized position for a sphere)
    // We use a simple random jitter here. For smoother rocks, we'd use Perlin noise,
    // but random jitter is usually enough for small asteroids.
    const deform = 1.0 + (Math.random() - 0.5) * amount;
    vertex.multiplyScalar(deform);
    posAttribute.setXYZ(i, vertex.x, vertex.y, vertex.z);
  }
  // Re-compute normals so lighting looks correct on the jagged surface
  geometry.computeVertexNormals();
  return geometry;
}

export function createAsteroidSystem(planetMesh, config) {
  // Config defaults
  const conf = config || {
    minCount: 4, maxCount: 8,
    minSize: 0.3, maxSize: 0.7,
    orbitDistanceMin: 1.5, orbitDistanceMax: 4.0,
    orbitSpeedMin: 0.2, orbitSpeedMax: 0.8,
    ruggedness: 0.2
  };

  const asteroids = [];
  const count = Math.floor(rand(conf.minCount, conf.maxCount));

  // 1. Define the Orbit Ring (A spline concept)
  // We want a ring around the equator (XZ plane relative to planet).
  // We don't need a visible line, just the math.

  for (let i = 0; i < count; i++) {
    // Randomize size
    const r = rand(conf.minSize, conf.maxSize);

    // Create Geometry
    let geo = new THREE.SphereGeometry(r, 7, 6); // Low poly for jagged look
    ruggedizeGeometry(geo, conf.ruggedness);

    const mat = new THREE.MeshStandardMaterial({
        color: 0x888888,
        roughness: 0.9,
        flatShading: true // Low poly look
    });

    const mesh = new THREE.Mesh(geo, mat);

    // 2. Setup Orbit Logic
    // Distance from planet center
    const planetRadius = planetMesh.geometry.parameters.radius;
    const dist = planetRadius + rand(conf.orbitDistanceMin, conf.orbitDistanceMax);

    // Start Angle
    const angle = Math.random() * Math.PI * 2;

    // Orbit Speed (Radians per second)
    const speed = rand(conf.orbitSpeedMin, conf.orbitSpeedMax) * (Math.random() < 0.5 ? 1 : -1);

    // Initial position (Local to planet)
    mesh.position.set(Math.cos(angle) * dist, rand(-0.5, 0.5), Math.sin(angle) * dist);

    // Add to Planet (So it moves with it)
    planetMesh.add(mesh);

    asteroids.push({
      mesh,
      orbitRadius: dist,
      angle: angle,
      speed: speed,
      rotationAxis: new THREE.Vector3(Math.random(), Math.random(), Math.random()).normalize(),
      rotationSpeed: rand(0.5, conf.selfRotationSpeed),
      r: r // Collision radius
    });
  }

  return asteroids;
}

export function updateAsteroids(planetMesh, dt) {
  // We stored the asteroid data on the planetMesh.userData for convenience
  const data = planetMesh.userData.asteroids;
  if (!data) return;

  data.forEach(a => {
    // 1. Orbit Update (Smooth circular motion)
    a.angle += a.speed * dt;

    // Update local position relative to planet
    // This creates a perfect ring orbit that follows the planet smoothly
    a.mesh.position.x = Math.cos(a.angle) * a.orbitRadius;
    a.mesh.position.z = Math.sin(a.angle) * a.orbitRadius;

    // 2. Self Rotation (Tumbling)
    a.mesh.rotateOnAxis(a.rotationAxis, a.rotationSpeed * dt);
  });
}

// Global collision check (World Space)
export function checkShipCollision(ship, allAsteroids) {
  const shipPos = ship.mesh.position;
  const worldPos = new THREE.Vector3();

  for (const a of allAsteroids) {
    // Get asteroid real world position
    a.mesh.getWorldPosition(worldPos);

    const dx = worldPos.x - shipPos.x;
    const dz = worldPos.z - shipPos.z;
    // Simple sphere collision
    const rr = (ship.radius + a.r) * (ship.radius + a.r);

    // Optimistic height check first
    if (Math.abs(worldPos.y - shipPos.y) < 3.0) {
        if (dx * dx + dz * dz < rr) return true;
    }
  }
  return false;
}