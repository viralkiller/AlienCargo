// static/js/blackhole/three/moons.js
import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { rand } from "../shared/math.js";

// Helper to noise-deform a sphere (Rugged look)
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

export function createMoonSystem(planetMesh, config) {
  const conf = config || {
    minCount: 1, maxCount: 3,
    minSize: 0.5, maxSize: 1.2,
    orbitDistanceMin: 1.5, orbitDistanceMax: 3.0,
    orbitSpeedMin: 0.4, orbitSpeedMax: 1.2,
    ruggedness: 0.2
  };

  const moons = [];
  const count = Math.floor(rand(conf.minCount, conf.maxCount));

  for (let i = 0; i < count; i++) {
    const r = rand(conf.minSize, conf.maxSize);

    // Create Geometry
    let geo = new THREE.SphereGeometry(r, 7, 6);
    ruggedizeGeometry(geo, conf.ruggedness);

    const mat = new THREE.MeshStandardMaterial({
        color: 0xaaaaaa,
        roughness: 0.8,
        flatShading: true
    });

    const mesh = new THREE.Mesh(geo, mat);

    // Orbit Logic
    const planetRadius = planetMesh.geometry.parameters.radius;
    const dist = planetRadius + rand(conf.orbitDistanceMin, conf.orbitDistanceMax);
    const angle = Math.random() * Math.PI * 2;
    const speed = rand(conf.orbitSpeedMin, conf.orbitSpeedMax) * (Math.random() < 0.5 ? 1 : -1);

    // Initial Pos
    mesh.position.set(Math.cos(angle) * dist, rand(-0.2, 0.2), Math.sin(angle) * dist);

    planetMesh.add(mesh); // Attach to planet

    moons.push({
      mesh,
      orbitRadius: dist,
      angle: angle,
      speed: speed,
      rotationAxis: new THREE.Vector3(Math.random(), Math.random(), Math.random()).normalize(),
      rotationSpeed: rand(0.5, 2.0),
      r: r // Collision radius
    });
  }
  return moons;
}

export function updateMoons(planetMesh, dt) {
  const data = planetMesh.userData.moons;
  if (!data) return;

  data.forEach(m => {
    // Orbit
    m.angle += m.speed * dt;
    m.mesh.position.x = Math.cos(m.angle) * m.orbitRadius;
    m.mesh.position.z = Math.sin(m.angle) * m.orbitRadius;

    // Tumble
    m.mesh.rotateOnAxis(m.rotationAxis, m.rotationSpeed * dt);
  });
}