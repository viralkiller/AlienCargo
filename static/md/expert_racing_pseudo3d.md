<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expert Racing Pseudo 3D Example</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #111;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            color: white;
            font-family: sans-serif;
            overflow: hidden;
        }
        #game-container {
            position: relative;
            box-shadow: 0 0 20px rgba(0,0,0,0.8);
        }
        /* UI overlay handled primarily in JS per guidelines, minimal CSS here */
    </style>
    <script src="https://cdn.jsdelivr.net/npm/phaser@3.55.2/dist/phaser.min.js"></script>
</head>
<body>

<div id="game-container"></div>

<script>
    // System Constants
    const GAME_WIDTH = 1280;
    const GAME_HEIGHT = 720;

    // Track & 3D Math Constants
    const SEGMENT_LENGTH = 200;
    const RUMBLE_LENGTH = 3;
    const ROAD_WIDTH = 2000;
    const CAMERA_HEIGHT = 1000;
    const CAMERA_DEPTH = 1 / Math.tan((100 / 2) * Math.PI / 180); // FOV
    const DRAW_DISTANCE = 300;

    const COLORS = {
        LIGHT: { road: 0x6b6b6b, grass: 0x10aa10, rumble: 0x555555, lane: 0xcccccc },
        DARK:  { road: 0x6b6b6b, grass: 0x009a00, rumble: 0xbb1111, lane: 0x6b6b6b },
        SKY: 0x72D7EE
    };

    class PlayScene extends Phaser.Scene {
        constructor() {
            super('PlayScene');
            this.segments = [];
            this.cameraZ = 0;
            this.playerX = 0;
            this.speed = 0;
            this.maxSpeed = SEGMENT_LENGTH * 60; // Approx 12000
            this.accel = this.maxSpeed / 50;
            this.breaking = -this.maxSpeed;
            this.decel = -this.maxSpeed / 50;
            this.offRoadDecel = -this.maxSpeed / 2;
            this.offRoadLimit = this.maxSpeed / 4;
            this.centrifugal = 0.3;

            this.trackLength = 0;
            this.graphics = null;
            this.keys = {};
        }

        preload() {
            console.log("[SYSTEM] Preloading assets...");
            // Generate a simple blocky car sprite texture programmatically
            let carGraphics = this.make.graphics({x: 0, y: 0, add: false});
            carGraphics.fillStyle(0xff0000, 1);
            carGraphics.fillRect(0, 20, 160, 40); // Body
            carGraphics.fillStyle(0x000000, 1);
            carGraphics.fillRect(20, 60, 30, 20); // Left tire
            carGraphics.fillRect(110, 60, 30, 20); // Right tire
            carGraphics.fillStyle(0x88ccff, 1);
            carGraphics.fillRect(30, 0, 100, 20); // Windshield
            carGraphics.generateTexture('playerCar', 160, 80);
            console.log("[SYSTEM] Assets preloaded.");
        }

        create() {
            console.log("[SCENE] PlayScene initialized.");

            // Background
            this.add.rectangle(GAME_WIDTH/2, GAME_HEIGHT/2, GAME_WIDTH, GAME_HEIGHT, COLORS.SKY);

            // Graphics object for drawing the 3D road
            this.graphics = this.add.graphics();

            // UI Layer
            this.createUI();

            // Track Generation
            this.resetRoad();

            // Input Handlers
            this.keys = this.input.keyboard.createCursorKeys();
            this.setupInputLogging();

            // Player Sprite
            this.playerSprite = this.add.sprite(GAME_WIDTH / 2, GAME_HEIGHT - 80, 'playerCar');
            this.playerSprite.setOrigin(0.5, 1);
        }

        createUI() {
            // Complex UI elements built in JS
            this.hudText = this.add.text(20, 20, 'SPEED: 0 km/h', {
                fontFamily: 'Courier',
                fontSize: '32px',
                color: '#ffffff',
                backgroundColor: '#000000'
            });
            this.hudText.setPadding(10, 10, 10, 10);

            // Interactive UI Button example (Start/Reset)
            const resetBtn = this.add.text(GAME_WIDTH - 150, 20, '[ RESTART ]', {
                fontFamily: 'Courier',
                fontSize: '24px',
                color: '#ffaa00',
                backgroundColor: '#222222'
            }).setInteractive({ useHandCursor: true });

            resetBtn.setPadding(10, 10, 10, 10);

            resetBtn.on('pointerdown', () => {
                console.log("[UI EVENT] Pointer Down: Reset Button Clicked.");
                this.cameraZ = 0;
                this.speed = 0;
                this.playerX = 0;
            });

            resetBtn.on('pointerover', () => resetBtn.setStyle({ color: '#ffffff' }));
            resetBtn.on('pointerout', () => resetBtn.setStyle({ color: '#ffaa00' }));
        }

        setupInputLogging() {
            this.input.keyboard.on('keydown-UP', () => console.log("[INPUT] Action: Accelerate (UP pressed)"));
            this.input.keyboard.on('keyup-UP', () => console.log("[INPUT] Action: Stop Accelerate (UP released)"));
            this.input.keyboard.on('keydown-DOWN', () => console.log("[INPUT] Action: Brake (DOWN pressed)"));
            this.input.keyboard.on('keydown-LEFT', () => console.log("[INPUT] Action: Steer Left (LEFT pressed)"));
            this.input.keyboard.on('keydown-RIGHT', () => console.log("[INPUT] Action: Steer Right (RIGHT pressed)"));
        }

        resetRoad() {
            console.log("[GAME LOGIC] Generating Track...");
            this.segments = [];
            for (let n = 0; n < 500; n++) {
                this.segments.push({
                    index: n,
                    p1: { world: { x: 0, y: 0, z: n * SEGMENT_LENGTH }, camera: {}, screen: {} },
                    p2: { world: { x: 0, y: 0, z: (n + 1) * SEGMENT_LENGTH }, camera: {}, screen: {} },
                    curve: (n > 100 && n < 300) ? 2 : ((n > 350) ? -1.5 : 0), // Simple curves
                    color: Math.floor(n / RUMBLE_LENGTH) % 2 ? COLORS.DARK : COLORS.LIGHT
                });
            }
            this.segments[this.segments.length - 1].color = { road: 0xffffff, grass: 0x000000, rumble: 0xffffff, lane: 0xffffff }; // Finish line
            this.trackLength = this.segments.length * SEGMENT_LENGTH;
            console.log(`[GAME LOGIC] Track generated. Length: ${this.segments.length} segments.`);
        }

        update(time, delta) {
            let dt = delta / 1000;

            // Movement Logic
            let playerSegment = this.findSegment(this.cameraZ + CAMERA_HEIGHT);
            let speedPercent = this.speed / this.maxSpeed;
            let dx = dt * 2 * speedPercent;

            if (this.keys.left.isDown) {
                this.playerX -= dx;
            } else if (this.keys.right.isDown) {
                this.playerX += dx;
            }

            // Centrifugal force
            this.playerX -= (dx * speedPercent * playerSegment.curve * this.centrifugal);

            if (this.keys.up.isDown) {
                this.speed = Phaser.Math.Clamp(this.speed + this.accel * dt, 0, this.maxSpeed);
            } else if (this.keys.down.isDown) {
                this.speed = Phaser.Math.Clamp(this.speed + this.breaking * dt, 0, this.maxSpeed);
            } else {
                this.speed = Phaser.Math.Clamp(this.speed + this.decel * dt, 0, this.maxSpeed);
            }

            // Offroad deceleration
            if ((this.playerX < -1 || this.playerX > 1) && this.speed > this.offRoadLimit) {
                this.speed = Phaser.Math.Clamp(this.speed + this.offRoadDecel * dt, 0, this.maxSpeed);
            }

            this.playerX = Phaser.Math.Clamp(this.playerX, -2, 2);
            this.cameraZ = (this.cameraZ + (this.speed * dt)) % this.trackLength;

            // Update HUD
            this.hudText.setText(`SPEED: ${Math.floor(this.speed / 100)} km/h`);

            this.renderTrack();
        }

        findSegment(z) {
            return this.segments[Math.floor(z / SEGMENT_LENGTH) % this.segments.length];
        }

        project(p, cameraX, cameraY, cameraZ, cameraDepth, width, height, roadWidth) {
            p.camera.x = (p.world.x || 0) - cameraX;
            p.camera.y = (p.world.y || 0) - cameraY;
            p.camera.z = (p.world.z || 0) - cameraZ;
            p.screen.scale = cameraDepth / p.camera.z;
            p.screen.x = Math.round((width / 2) + (p.screen.scale * p.camera.x * width / 2));
            p.screen.y = Math.round((height / 2) - (p.screen.scale * p.camera.y * height / 2));
            p.screen.w = Math.round((p.screen.scale * roadWidth * width / 2));
        }

        renderTrack() {
            this.graphics.clear();

            let baseSegment = this.findSegment(this.cameraZ);
            let maxy = GAME_HEIGHT;
            let x = 0;
            let dx = -(baseSegment.curve * (this.cameraZ % SEGMENT_LENGTH) / SEGMENT_LENGTH);

            for (let n = 0; n < DRAW_DISTANCE; n++) {
                let segment = this.segments[(baseSegment.index + n) % this.segments.length];
                segment.looped = segment.index < baseSegment.index;

                this.project(
                    segment.p1,
                    (this.playerX * ROAD_WIDTH) - x,
                    CAMERA_HEIGHT,
                    this.cameraZ - (segment.looped ? this.trackLength : 0),
                    CAMERA_DEPTH, GAME_WIDTH, GAME_HEIGHT, ROAD_WIDTH
                );

                this.project(
                    segment.p2,
                    (this.playerX * ROAD_WIDTH) - x - dx,
                    CAMERA_HEIGHT,
                    this.cameraZ - (segment.looped ? this.trackLength : 0),
                    CAMERA_DEPTH, GAME_WIDTH, GAME_HEIGHT, ROAD_WIDTH
                );

                x = x + dx;
                dx = dx + segment.curve;

                if ((segment.p1.camera.z <= CAMERA_DEPTH) || (segment.p2.screen.y >= maxy)) {
                    continue;
                }

                this.drawSegment(
                    GAME_WIDTH,
                    segment.p1.screen.x, segment.p1.screen.y, segment.p1.screen.w,
                    segment.p2.screen.x, segment.p2.screen.y, segment.p2.screen.w,
                    segment.color
                );

                maxy = segment.p2.screen.y;
            }
        }

        drawSegment(width, x1, y1, w1, x2, y2, w2, color) {
            let r1 = w1 / Math.max(6, 2 * 1);
            let r2 = w2 / Math.max(6, 2 * 1);
            let l1 = w1 / Math.max(32, 8 * 1);
            let l2 = w2 / Math.max(32, 8 * 1);

            // Draw grass
            this.graphics.fillStyle(color.grass, 1);
            this.graphics.fillRect(0, y2, width, y1 - y2);

            // Draw rumble strip
            this.drawPolygon(x1 - w1 - r1, y1, x1 - w1, y1, x2 - w2, y2, x2 - w2 - r2, y2, color.rumble);
            this.drawPolygon(x1 + w1 + r1, y1, x1 + w1, y1, x2 + w2, y2, x2 + w2 + r2, y2, color.rumble);

            // Draw road
            this.drawPolygon(x1 - w1, y1, x1 + w1, y1, x2 + w2, y2, x2 - w2, y2, color.road);

            // Draw lane
            if (color.lane) {
                let lanew1 = w1 * 2 / 100;
                let lanew2 = w2 * 2 / 100;
                let lanex1 = x1;
                let lanex2 = x2;
                this.drawPolygon(lanex1 - lanew1/2, y1, lanex1 + lanew1/2, y1, lanex2 + lanew2/2, y2, lanex2 - lanew2/2, y2, color.lane);
            }
        }

        drawPolygon(x1, y1, x2, y2, x3, y3, x4, y4, color) {
            this.graphics.fillStyle(color, 1);
            this.graphics.beginPath();
            this.graphics.moveTo(x1, y1);
            this.graphics.lineTo(x2, y2);
            this.graphics.lineTo(x3, y3);
            this.graphics.lineTo(x4, y4);
            this.graphics.closePath();
            this.graphics.fillPath();
        }
    }

    const config = {
        type: Phaser.AUTO,
        width: GAME_WIDTH,
        height: GAME_HEIGHT,
        parent: 'game-container',
        scene: [PlayScene],
        physics: {
            default: 'arcade',
            arcade: { debug: false }
        }
    };

    console.log("[SYSTEM] Booting Phaser Game Engine...");
    const game = new Phaser.Game(config);

</script>
</body>
</html>
