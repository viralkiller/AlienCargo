// Ship.js
import * as THREE from 'three';

export class Ship {
    constructor(scene) {
        this.mesh = new THREE.Group();

        // 80s Vector Graphic style ship
        const hullGeo = new THREE.ConeGeometry(1, 3, 4);
        hullGeo.rotateX(Math.PI / 2);
        const hullMat = new THREE.MeshStandardMaterial({ color: 0x00ffcc, wireframe: true, emissive: 0x005544 });
        this.mesh.add(new THREE.Mesh(hullGeo, hullMat));

        scene.add(this.mesh);

        // Physics variables
        this.radius = 45;
        this.angle = Math.PI / 2;
        this.dr = 0; // Radial velocity
        this.dAngle = 0; // Orbital velocity

        this.keys = { left: false, right: false, up: false };

        window.addEventListener('keydown', (e) => this.handleKey(e, true));
        window.addEventListener('keyup', (e) => this.handleKey(e, false));
    }

    handleKey(e, isDown) {
        if (e.code === 'ArrowLeft' || e.code === 'KeyA') this.keys.left = isDown;
        if (e.code === 'ArrowRight' || e.code === 'KeyD') this.keys.right = isDown;
        if (e.code === 'ArrowUp' || e.code === 'KeyW') this.keys.up = isDown;
    }

    update(gravity) {
        // Flawless Kinetic Control: Add acceleration, apply friction
        if (this.keys.left) this.dAngle += 0.0015;
        if (this.keys.right) this.dAngle -= 0.0015;
        this.dAngle *= 0.94; // Rotational friction

        // Escape thrust vs Gravity
        if (this.keys.up) this.dr += 0.08;
        this.dr -= gravity;
        this.dr *= 0.96; // Radial friction (keeps movement snappy)

        this.angle += this.dAngle;
        this.radius += this.dr;

        // Cap escape distance
        if (this.radius > 60) {
            this.radius = 60;
            this.dr = 0;
        }

        // Height mapping for the gravity well funnel
        let y = -2;
        if (this.radius < 30) y = -400 / (Math.max(this.radius, 1) + 5) + 12;

        this.mesh.position.set(
            Math.cos(this.angle) * this.radius,
            y + 1.5,
            Math.sin(this.angle) * this.radius
        );

        // Banking animation based on velocity
        this.mesh.rotation.y = -this.angle;
        this.mesh.rotation.z = -this.dAngle * 15; // Lean into turns
    }
}