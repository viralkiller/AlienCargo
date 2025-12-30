import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

export function initThree(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 1);

  const scene = new THREE.Scene();

  // [NEW] Fog for smooth fade in.
  // Color 0x000000 (Black).
  // Start: 120 (Just beyond the ship), End: 450 (Fade out completely)
  scene.fog = new THREE.Fog(0x000000, 120, 450);

  // [NEW] Increased Far Plane to 6000 to prevent clipping before fog ends
  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 6000);
  camera.rotation.order = "YXZ";
  resetCameraSym(camera);

  scene.add(new THREE.HemisphereLight(0xffffff, 0x101018, 0.8));
  const dir = new THREE.DirectionalLight(0xffffff, 0.6);
  dir.position.set(20, 40, 10);
  scene.add(dir);

  return { renderer, scene, camera };
}

export function resetCameraSym(camera) {
  camera.position.set(0, 13.5, 27.5);
  camera.lookAt(0, 0, 0);
}