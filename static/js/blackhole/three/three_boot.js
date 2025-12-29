import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

export function initThree(canvas) {
  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setClearColor(0x000000, 1);

  const scene = new THREE.Scene();

  const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 5000);
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
