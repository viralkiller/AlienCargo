// GameLogic.js
import * as THREE from 'three';

export class GameLogic {
    constructor(scene, ship, audioCtx) {
        this.scene = scene;
        this.ship = ship;
        this.audioCtx = audioCtx;

        this.projectiles = [];
        this.enemyProjectiles = [];
        this.enemies = [];
        this.packets = [];
        this.score = 0;

        this.gravity = 0.025; // Constant pull
        this.isGameOver = false;

        // 80s Neon Materials
        this.projMat = new THREE.MeshStandardMaterial({ color: 0xffff00, emissive: 0xffff00, emissiveIntensity: 2 });
        this.enemyProjMat = new THREE.MeshStandardMaterial({ color: 0xff0000, emissive: 0xff0000 });
        this.rockMat = new THREE.MeshStandardMaterial({ color: 0x6b4226, wireframe: true });

        this.packetMat = new THREE.MeshStandardMaterial({ color: 0x00ffff, emissive: 0x00ffff, emissiveIntensity: 2 });

        this.lastTensionBeep = 0;
        this.grazeUI = document.getElementById('graze-ui');
    }

    // --- AUDIO SYSTEM: Dynamic Tension Engine ---
    playSynth(freq, type, duration, vol = 0.1) {
        if (!this.audioCtx) return;
        const osc = this.audioCtx.createOscillator();
        const gain = this.audioCtx.createGain();
        osc.type = type;
        osc.frequency.setValueAtTime(freq, this.audioCtx.currentTime);
        // Quick fade out for punchy retro sound
        gain.gain.setValueAtTime(vol, this.audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, this.audioCtx.currentTime + duration);
        osc.connect(gain);
        gain.connect(this.audioCtx.destination);
        osc.start();
        osc.stop(this.audioCtx.currentTime + duration);
    }

    triggerGrazeUI() {
        this.grazeUI.style.opacity = 1;
        this.grazeUI.style.transform = `translate(-50%, -50%) scale(${1 + Math.random() * 0.5})`;
        setTimeout(() => { this.grazeUI.style.opacity = 0; }, 200);
    }

    shoot() {
        if (this.isGameOver) return;
        this.playSynth(880, 'square', 0.1, 0.05); // Laser sound

        let target = null;
        let minDist = Infinity;
        for (let e of this.enemies) {
            let d = e.mesh.position.distanceTo(this.ship.mesh.position);
            if (d < minDist) { minDist = d; target = e; }
        }

        const geo = new THREE.CylinderGeometry(0.1, 0.1, 4, 8);
        geo.rotateX(Math.PI / 2);
        const proj = new THREE.Mesh(geo, this.projMat);
        proj.position.copy(this.ship.mesh.position);

        this.projectiles.push({
            mesh: proj,
            radius: this.ship.radius,
            angle: this.ship.angle,
            dr: 1.0,
            dAngle: this.ship.dAngle + 0.02,
            target: target
        });
        this.scene.add(proj);
    }

    spawnEnemy() {
        if (this.isGameOver) return;

        // Pac-Man style deterministic personalities
        const types = ['rock', 'chaser', 'ambusher', 'erratic'];
        const type = types[Math.floor(Math.random() * types.length)];

        let mesh;
        let matColor = 0xff0000;

        if (type === 'rock') {
            mesh = new THREE.Mesh(new THREE.DodecahedronGeometry(1.5, 0), this.rockMat);
            mesh.rotation.set(Math.random(), Math.random(), Math.random());
        } else {
            mesh = new THREE.Group();
            const hullGeo = new THREE.ConeGeometry(0.8, 2.5, 4);
            hullGeo.rotateX(Math.PI / 2);

            if (type === 'chaser') matColor = 0xff0000; // Red
            if (type === 'ambusher') matColor = 0xff00ff; // Pink
            if (type === 'erratic') matColor = 0xffaa00; // Orange

            const mat = new THREE.MeshStandardMaterial({ color: matColor, wireframe: true, emissive: matColor, emissiveIntensity: 0.5 });
            mesh.add(new THREE.Mesh(hullGeo, mat));
        }

        const spawnRad = 70;
        const spawnAng = Math.random() * Math.PI * 2;
        mesh.position.set(Math.cos(spawnAng) * spawnRad, -1, Math.sin(spawnAng) * spawnRad);

        this.enemies.push({ mesh, radius: spawnRad, angle: spawnAng, type, stateTimer: 0 });
        this.scene.add(mesh);
    }

    spawnPacket(pos, angle, radius) {
        const packet = new THREE.Mesh(new THREE.BoxGeometry(1.2, 1.2, 1.2), this.packetMat);
        packet.position.copy(pos);
        this.packets.push({ mesh: packet, angle: angle, radius: radius });
        this.scene.add(packet);
    }

    update() {
        if (this.isGameOver) return;
        const now = Date.now();

        // Dynamic Audio: Heartbeat speeds up as you fall in
        let beepInterval = Math.max(100, this.ship.radius * 15);
        if (now - this.lastTensionBeep > beepInterval) {
            this.playSynth(110 - (50 - this.ship.radius), 'sawtooth', 0.1, 0.05);
            this.lastTensionBeep = now;
        }

        // --- Player Projectiles ---
        for (let i = this.projectiles.length - 1; i >= 0; i--) {
            const p = this.projectiles[i];
            p.dr -= 0.012; // Gravity bends lasers

            if (p.target && this.enemies.includes(p.target)) {
                let tAngle = Math.atan2(p.target.mesh.position.z, p.target.mesh.position.x);
                let diff = tAngle - p.angle;
                while(diff < -Math.PI) diff += Math.PI * 2;
                while(diff > Math.PI) diff -= Math.PI * 2;
                p.dAngle += diff * 0.02; // Homing math
            }

            p.radius += p.dr;
            p.angle += p.dAngle;

            let y = p.radius < 30 ? -400 / (Math.max(p.radius, 1) + 5) + 12 : -2;
            p.mesh.position.set(Math.cos(p.angle) * p.radius, y + 1.5, Math.sin(p.angle) * p.radius);

            let nx = Math.cos(p.angle + p.dAngle) * (p.radius + p.dr);
            let nz = Math.sin(p.angle + p.dAngle) * (p.radius + p.dr);
            p.mesh.lookAt(nx, y + 1.5, nz);

            if (p.radius > 120 || p.radius < 2) {
                this.scene.remove(p.mesh);
                this.projectiles.splice(i, 1);
            }
        }

        // --- Enemy Projectiles & GRAZE MECHANIC ---
        for (let i = this.enemyProjectiles.length - 1; i >= 0; i--) {
            const ep = this.enemyProjectiles[i];
            ep.mesh.position.add(ep.velocity);

            let distToPlayer = ep.mesh.position.distanceTo(this.ship.mesh.position);

            if (distToPlayer < 2.0) {
                // Hit!
                this.playSynth(150, 'sawtooth', 0.5, 0.2); // Crash sound
                this.ship.radius -= 6; // Knocked inward
                document.body.classList.add('shake');
                setTimeout(()=>document.body.classList.remove('shake'), 200);
                this.scene.remove(ep.mesh);
                this.enemyProjectiles.splice(i, 1);
                continue;
            } else if (distToPlayer < 4.5 && !ep.grazed) {
                // GRAZE: The "Near Miss" psychological loop
                ep.grazed = true;
                this.score += 50;
                this.playSynth(1200, 'square', 0.1, 0.02); // High pitched ding
                this.triggerGrazeUI();
            }

            if (ep.mesh.position.length() < 5) {
                this.scene.remove(ep.mesh);
                this.enemyProjectiles.splice(i, 1);
            }
        }

        // --- Enemies Logic (Personality Determinism) ---
        for (let i = this.enemies.length - 1; i >= 0; i--) {
            const e = this.enemies[i];
            e.stateTimer++;

            // Base gravity pull
            let radSpeed = 0.05;
            let angSpeed = 0.01;

            // Apply specific AI rules to mimic organic chaos
            if (e.type === 'rock') {
                e.mesh.rotation.x += 0.02;
                e.mesh.rotation.y += 0.01;
            }
            else if (e.type === 'chaser') {
                // Red Ghost: Tries to align angle directly with player
                let diff = this.ship.angle - e.angle;
                while(diff < -Math.PI) diff += Math.PI * 2;
                while(diff > Math.PI) diff -= Math.PI * 2;
                angSpeed = diff > 0 ? 0.015 : -0.015;
            }
            else if (e.type === 'ambusher') {
                // Pink Ghost: Tries to go to where player is heading (predictive)
                let predictedAngle = this.ship.angle + (this.ship.dAngle * 20);
                let diff = predictedAngle - e.angle;
                while(diff < -Math.PI) diff += Math.PI * 2;
                while(diff > Math.PI) diff -= Math.PI * 2;
                angSpeed = diff > 0 ? 0.02 : -0.02;
            }
            else if (e.type === 'erratic') {
                // Orange Ghost: Periodic speed bursts
                if (e.stateTimer % 120 < 40) {
                    radSpeed = 0.15; angSpeed = 0.03;
                } else {
                    radSpeed = 0.02; angSpeed = 0.005;
                }
            }

            e.radius -= radSpeed;
            e.angle += angSpeed;

            let y = e.radius < 30 ? -400 / (e.radius + 5) + 12 : -2;
            e.mesh.position.set(Math.cos(e.angle) * e.radius, y + 1.5, Math.sin(e.angle) * e.radius);

            if (e.type !== 'rock') {
                e.mesh.rotation.y = -e.angle;
                // Asymmetric firing rate to prevent predictability
                let fireChance = (e.type === 'chaser') ? 0.01 : (e.type === 'ambusher' ? 0.015 : 0.02);
                if (Math.random() < fireChance) {
                    const epMesh = new THREE.Mesh(new THREE.SphereGeometry(0.4, 4, 4), this.enemyProjMat);
                    epMesh.position.copy(e.mesh.position);
                    const dir = new THREE.Vector3().subVectors(this.ship.mesh.position, e.mesh.position).normalize();
                    this.enemyProjectiles.push({ mesh: epMesh, velocity: dir.multiplyScalar(0.7), grazed: false });
                    this.scene.add(epMesh);
                    this.playSynth(300, 'square', 0.1, 0.05); // Enemy shoot sound
                }
            }

            // Player collides with enemy
            if (e.mesh.position.distanceTo(this.ship.mesh.position) < 3.5) {
                this.playSynth(100, 'sawtooth', 0.8, 0.3);
                this.ship.radius -= 10;
                this.scene.remove(e.mesh);
                this.enemies.splice(i, 1);
                continue;
            }

            // Hit by player laser
            let destroyed = false;
            for (let j = this.projectiles.length - 1; j >= 0; j--) {
                const p = this.projectiles[j];
                if (e.mesh.position.distanceTo(p.mesh.position) < 4.0) {
                    this.playSynth(200, 'square', 0.2, 0.1); // Enemy explode
                    this.score += (e.type === 'rock') ? 10 : 30;
                    if (e.type !== 'rock') this.spawnPacket(e.mesh.position, e.angle, e.radius);
                    this.scene.remove(e.mesh);
                    this.scene.remove(p.mesh);
                    this.enemies.splice(i, 1);
                    this.projectiles.splice(j, 1);
                    destroyed = true;
                    break;
                }
            }

            if (!destroyed && e.radius < 5) {
                this.scene.remove(e.mesh);
                this.enemies.splice(i, 1);
            }
        }

        // --- Packets Logic ---
        for (let i = this.packets.length - 1; i >= 0; i--) {
            const pkt = this.packets[i];
            pkt.angle += 0.01;
            pkt.radius -= 0.03;

            let y = pkt.radius < 30 ? -400 / (pkt.radius + 5) + 12 : -2;
            pkt.mesh.position.set(Math.cos(pkt.angle) * pkt.radius, y + 1, Math.sin(pkt.angle) * pkt.radius);
            pkt.mesh.rotation.y += 0.05;
            pkt.mesh.rotation.x += 0.05;

            if (pkt.mesh.position.distanceTo(this.ship.mesh.position) < 4) {
                this.playSynth(600, 'sine', 0.2, 0.1); // Powerup sound
                this.ship.radius += 12; // Outward thrust
                this.score += 50;
                this.scene.remove(pkt.mesh);
                this.packets.splice(i, 1);
                continue;
            }

            if (pkt.radius < 5) {
                this.scene.remove(pkt.mesh);
                this.packets.splice(i, 1);
            }
        }

        // Game Over condition
        if (this.ship.radius < 5) {
            this.playSynth(50, 'sawtooth', 2.0, 0.5); // Death boom
            this.isGameOver = true;
            document.getElementById('game-over').style.display = 'block';
            document.body.classList.remove('shake');
        }
    }
}