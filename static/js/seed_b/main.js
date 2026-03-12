// main.js
import * as THREE from 'three';
import { createBlackHole } from './BlackHole.js';
import { Ship } from './Ship.js';
import { GameLogic } from './GameLogic.js';

console.log("Main boot sequence initiated.");

let audioCtx = null;
let logic = null;
let ship = null;
let blackHoleMesh = null;
let isRunning = false;

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);
camera.position.set(0, 40, 60);
camera.lookAt(0, -10, 0);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setPixelRatio(window.devicePixelRatio);
document.body.appendChild(renderer.domElement);

const ambientLight = new THREE.AmbientLight(0x303040, 1.5);
scene.add(ambientLight);

const pointLight = new THREE.PointLight(0xffaa22, 10, 150);
pointLight.position.set(0, 5, 0);
scene.add(pointLight);

// UI bindings
const distEl = document.getElementById('distVal');
const scoreEl = document.getElementById('scoreVal');

document.getElementById('btnStart').addEventListener('click', () => {
    // 80s Audio requires user interaction to start AudioContext
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    document.getElementById('start-screen').style.display = 'none';
    document.getElementById('ui').style.display = 'block';

    startGame();
});

document.getElementById('btnRestart').addEventListener('click', () => {
    location.reload(); // "Go Again" loop
});

window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
});

function startGame() {
    blackHoleMesh = createBlackHole(scene);
    ship = new Ship(scene);
    logic = new GameLogic(scene, ship, audioCtx);

    window.addEventListener('keydown', (e) => {
        if (e.code === 'Space') logic.shoot();
    });

    setInterval(() => logic.spawnEnemy(), 1500);
    isRunning = true;
    animate();
}

function animate() {
    requestAnimationFrame(animate);
    if (!isRunning) return;

    blackHoleMesh.rotation.z += 0.002;

    if (!logic.isGameOver) {
        ship.update(logic.gravity);
        logic.update();

        // UI Updates
        let currentRadius = Math.max(0, Math.floor(ship.radius - 5));
        distEl.innerText = currentRadius;
        scoreEl.innerText = logic.score;

        // Visual Tension: Screen shake when near the horizon
        if (currentRadius < 10) {
            document.body.classList.add('shake');
        } else {
            document.body.classList.remove('shake');
        }
    }

    renderer.render(scene, camera);
}