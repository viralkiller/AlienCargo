import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";
import { input } from "./input_state.js";

const ray = new THREE.Raycaster();
const plane = new THREE.Plane(new THREE.Vector3(0, 1, 0), 0);
const _hit = new THREE.Vector3();

export function updateShip(ship, camera, renderer, dt) {
  const w = renderer.domElement.clientWidth;
  const h = renderer.domElement.clientHeight;

  // Bottom control box anchor (screen space)
  const cx = w / 2;
  const by = h - ship.state.boxBottom;

  // Persistent cursor inside box (screen space)
  if (ship.state.cursorX === undefined) ship.state.cursorX = cx;
  if (ship.state.cursorY === undefined) ship.state.cursorY = by - ship.state.boxHeight * 0.35;

  let dx = 0;
  let dy = 0;

  if (input.keys.has("ArrowLeft")) dx -= 1;
  if (input.keys.has("ArrowRight")) dx += 1;

  // IMPORTANT: Up should move the cursor UP (smaller sy) => forward in your chase view
  if (input.keys.has("ArrowUp")) dy -= 1;
  if (input.keys.has("ArrowDown")) dy += 1;

  if (!dx && !dy) return;

  // Normalize diagonal
  const len = Math.hypot(dx, dy) || 1;
  dx /= len;
  dy /= len;

  // Move cursor inside the box (accumulative!)
  const pxPerSec = ship.state.speedPx; // treat speedPx as cursor speed too
  ship.state.cursorX += dx * pxPerSec * dt;
  ship.state.cursorY += dy * pxPerSec * dt;

  // Clamp cursor to the red box
  const minX = cx - ship.state.boxWidth / 2;
  const maxX = cx + ship.state.boxWidth / 2;
  const minY = by - ship.state.boxHeight;
  const maxY = by;

  ship.state.cursorX = Math.max(minX, Math.min(maxX, ship.state.cursorX));
  ship.state.cursorY = Math.max(minY, Math.min(maxY, ship.state.cursorY));

  // Also clamp to window bounds (safety)
  ship.state.cursorX = Math.max(0, Math.min(w, ship.state.cursorX));
  ship.state.cursorY = Math.max(0, Math.min(h, ship.state.cursorY));

  // Debug (throttle a bit)
  if (Math.random() < 0.05) {
    console.log("[SHIP][CURSOR]", {
      dx: dx.toFixed(2),
      dy: dy.toFixed(2),
      cursorX: ship.state.cursorX.toFixed(1),
      cursorY: ship.state.cursorY.toFixed(1),
    });
  }

  // Screen -> ray -> plane hit
  ray.setFromCamera(
    new THREE.Vector2((ship.state.cursorX / w) * 2 - 1, -(ship.state.cursorY / h) * 2 + 1),
    camera
  );

  plane.constant = -ship.state.y;

  if (ray.ray.intersectPlane(plane, _hit)) {
    ship.mesh.position.set(_hit.x, ship.state.y, _hit.z);

    if (Math.random() < 0.03) {
      console.log("[SHIP][HIT]", {
        x: _hit.x.toFixed(2),
        z: _hit.z.toFixed(2),
      });
    }
  } else {
    console.warn("[SHIP] ray-plane miss");
  }
}
