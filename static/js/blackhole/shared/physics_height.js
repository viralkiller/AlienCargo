import * as THREE from "https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js";

// Must match grid_shader.js consts
const SOFTENING = 8.0;
const DEPTH_STRENGTH = 22.0;

// [TUNING] Smoother, gentle rolling waves
const NOISE_AMP = 3.0;    // Reduced from 5.0
const NOISE_FREQ = 0.02;  // Reduced from 0.05 (Longer wavelength)

// --- GLSL Hash / Noise Port ---
function fract(x) { return x - Math.floor(x); }

function hash(x, y) {
  const dot = x * 12.9898 + y * 78.233;
  const sin = Math.sin(dot);
  return fract(sin * 43758.5453);
}

function noise(x, y) {
  const ix = Math.floor(x);
  const iy = Math.floor(y);
  const fx = fract(x);
  const fy = fract(y);

  // Cubic Hermite Smoothing
  const ux = fx * fx * (3.0 - 2.0 * fx);
  const uy = fy * fy * (3.0 - 2.0 * fy);

  const a = hash(ix, iy);
  const b = hash(ix + 1, iy);
  const c = hash(ix, iy + 1);
  const d = hash(ix + 1, iy + 1);

  return (a * (1 - ux) + b * ux) * (1 - uy) +
         (c * (1 - ux) + d * ux) * uy;
}

function fbm(x, y) {
  let total = 0.0;
  let amp = 1.0;
  let freq = NOISE_FREQ;
  // 3 Octaves
  for(let i = 0; i < 3; i++) {
    total += noise(x * freq, y * freq) * amp;
    freq *= 2.0;
    amp *= 0.5;
  }
  return total;
}

// --- Main Surface Function ---
export function getSurfaceHeight(x, z, planets) {
  // 1. Gravity Wells
  let w = 0.0;
  if (planets) {
    for (const p of planets) {
      const dx = x - p.position.x;
      const dz = z - p.position.z;
      w += p.userData.mass / (dx * dx + dz * dz + SOFTENING);
    }
  }

  // 2. Terrain Noise
  const terrain = fbm(x, z) * NOISE_AMP;

  // 3. Combine
  return terrain - (w * DEPTH_STRENGTH);
}