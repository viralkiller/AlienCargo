<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Expert Fighting Versus Example</title>
    <style>
        body { margin: 0; padding: 0; background-color: #050505; display: flex; flex-direction: column; align-items: center; justify-content: center; height: 100vh; color: white; font-family: 'Courier New', Courier, monospace; overflow: hidden; }
        #game-wrapper { position: relative; width: 1280px; height: 720px; box-shadow: 0 0 20px rgba(0,0,0,0.8); }
        #game-ui { position: absolute; top: 0; left: 0; width: 100%; padding: 20px; box-sizing: border-box; display: flex; justify-content: space-between; align-items: flex-start; z-index: 10; pointer-events: none; }
        .player-hud { display: flex; flex-direction: column; width: 40%; }
        #p2-hud { align-items: flex-end; }
        .health-bar-bg { width: 100%; height: 30px; background: #333; border: 3px solid #ccc; box-shadow: 2px 2px 0 #000; position: relative; }
        .health-bar-fill { height: 100%; background: linear-gradient(to bottom, #ffeb3b, #ff9800); width: 100%; transition: width 0.1s ease-out; }
        #p1-health { transform-origin: left; }
        #p2-health { transform-origin: right; float: right; }
        .combo-counter { font-size: 24px; font-weight: bold; color: #ffeb3b; text-shadow: 2px 2px 0 #f44336; margin-top: 10px; opacity: 0; transition: opacity 0.2s; }
        #timer { font-size: 48px; font-weight: bold; text-shadow: 2px 2px 0 #000; width: 10%; text-align: center; }
        #debug-panel { margin-top: 10px; width: 1280px; font-size: 12px; color: #00ff00; background: #111; padding: 10px; box-sizing: border-box; height: 150px; overflow-y: scroll; border: 1px solid #333; }
    </style>
    <script src="https://cdn.jsdelivr.net/npm/phaser@3.55.2/dist/phaser.min.js"></script>
</head>
<body>

    <div id="game-wrapper">
        <div id="game-ui">
            <div class="player-hud" id="p1-hud">
                <div class="health-bar-bg"><div id="p1-health" class="health-bar-fill"></div></div>
                <div id="p1-combo" class="combo-counter">0 HIT COMBO</div>
            </div>
            <div id="timer">99</div>
            <div class="player-hud" id="p2-hud">
                <div class="health-bar-bg"><div id="p2-health" class="health-bar-fill"></div></div>
                <div id="p2-combo" class="combo-counter">0 HIT COMBO</div>
            </div>
        </div>
        <div id="game-container"></div>
    </div>

    <div id="debug-panel"><strong>ENGINE LOG:</strong><br></div>

    <script>
        // --- CONSTANTS & CONFIG ---
        const GAME_WIDTH = 1280;
        const GAME_HEIGHT = 720;
        const GRAVITY = 2000;
        const GROUND_Y = GAME_HEIGHT - 50;

        const STATES = {
            IDLE: 'idle', WALK: 'walk', JUMP: 'jump',
            CROUCH: 'crouch', ATTACK: 'attack',
            HITSTUN: 'hitstun', BLOCKSTUN: 'blockstun', KO: 'ko'
        };

        const LOG = (msg) => {
            const panel = document.getElementById('debug-panel');
            panel.innerHTML += `[${new Date().toISOString().split('T')[1].slice(0,-1)}] ${msg}<br>`;
            panel.scrollTop = panel.scrollHeight;
        };

        // --- FIGHTER CLASS ---
        // Encapsulates all logic, state, and physics for a single character
        class Fighter {
            constructor(scene, x, y, key, isPlayer1) {
                this.scene = scene;
                this.isP1 = isPlayer1;
                this.key = key;

                // Stats
                this.maxHealth = 1000;
                this.health = this.maxHealth;
                this.walkSpeed = 300;
                this.jumpVelocity = -900;

                // State Engine
                this.currentState = STATES.IDLE;
                this.stateTimer = 0;
                this.comboCount = 0;

                // Frame Data tracking (Startup, Active, Recovery)
                this.currentAttack = null;

                // Physics Sprite
                this.sprite = scene.physics.add.sprite(x, y, key);
                this.sprite.setCollideWorldBounds(true);
                this.sprite.setBounce(0);
                this.sprite.setDragX(1500); // Friction

                // Hitbox (Offensive)
                this.hitbox = scene.physics.add.sprite(x, y, 'hitbox_tex');
                this.hitbox.setVisible(false);
                this.hitbox.body.setAllowGravity(false);

                // Opponent Reference (set later)
                this.opponent = null;

                LOG(`Fighter ${this.key} initialized at (${x}, ${y}).`);
            }

            setOpponent(opponentFighter) {
                this.opponent = opponentFighter;
            }

            update(inputs) {
                if (this.currentState === STATES.KO) return;

                const onGround = this.sprite.body.touching.down;
                this.faceOpponent();
                this.updateHitboxPosition();

                // State Machine Switch
                switch (this.currentState) {
                    case STATES.IDLE:
                    case STATES.WALK:
                    case STATES.CROUCH:
                        this.handleNeutralInput(inputs, onGround);
                        break;
                    case STATES.JUMP:
                        this.handleAirInput(inputs, onGround);
                        break;
                    case STATES.ATTACK:
                        this.processAttackFrameData();
                        break;
                    case STATES.HITSTUN:
                    case STATES.BLOCKSTUN:
                        this.processStun();
                        break;
                }
            }

            handleNeutralInput(inputs, onGround) {
                if (!onGround) {
                    this.changeState(STATES.JUMP);
                    return;
                }

                // Attacks take priority
                if (inputs.lightPunch && Phaser.Input.Keyboard.JustDown(inputs.lightPunch)) {
                    this.executeAttack({ damage: 50, startup: 4, active: 3, recovery: 10, hitstun: 15, blockstun: 10, pushback: 200, isHigh: true });
                    return;
                }
                if (inputs.heavyPunch && Phaser.Input.Keyboard.JustDown(inputs.heavyPunch)) {
                    this.executeAttack({ damage: 120, startup: 8, active: 4, recovery: 20, hitstun: 25, blockstun: 15, pushback: 400, isHigh: true });
                    return;
                }

                // Movement & Guard
                let isMoving = false;
                let isCrouching = inputs.down.isDown;

                if (isCrouching) {
                    this.sprite.setVelocityX(0);
                    this.sprite.setScale(1, 0.7); // Visual crouch
                    this.changeState(STATES.CROUCH);
                } else {
                    this.sprite.setScale(1, 1);
                    if (inputs.left.isDown) {
                        this.sprite.setVelocityX(-this.walkSpeed);
                        isMoving = true;
                    } else if (inputs.right.isDown) {
                        this.sprite.setVelocityX(this.walkSpeed);
                        isMoving = true;
                    }

                    if (inputs.up.isDown) {
                        this.sprite.setVelocityY(this.jumpVelocity);
                        this.changeState(STATES.JUMP);
                        LOG(`${this.key} Jumped.`);
                    } else {
                        this.changeState(isMoving ? STATES.WALK : STATES.IDLE);
                    }
                }
            }

            handleAirInput(inputs, onGround) {
                if (onGround) {
                    this.changeState(STATES.IDLE);
                    this.sprite.setVelocityX(0); // Stop momentum on land
                }
            }

            executeAttack(attackData) {
                this.changeState(STATES.ATTACK);
                this.currentAttack = { ...attackData, timer: 0, hasHit: false };
                this.sprite.setVelocityX(0);
                this.sprite.setTint(0xffaa00); // Visual indicator of attack
                LOG(`${this.key} executed attack. Startup: ${attackData.startup}f`);
            }

            processAttackFrameData() {
                if (!this.currentAttack) return;

                const atk = this.currentAttack;
                atk.timer++;

                // Startup Phase
                if (atk.timer < atk.startup) {
                    // Waiting for active frames
                }
                // Active Phase
                else if (atk.timer >= atk.startup && atk.timer < (atk.startup + atk.active)) {
                    this.hitbox.setVisible(true);

                    // Collision Check
                    if (!atk.hasHit && this.scene.physics.overlap(this.hitbox, this.opponent.sprite)) {
                        atk.hasHit = true;
                        this.opponent.receiveHit(atk, this);
                    }
                }
                // Recovery Phase
                else if (atk.timer >= (atk.startup + atk.active) && atk.timer < (atk.startup + atk.active + atk.recovery)) {
                    this.hitbox.setVisible(false);
                    this.sprite.clearTint();
                }
                // End Attack
                else {
                    this.hitbox.setVisible(false);
                    this.sprite.clearTint();
                    this.currentAttack = null;
                    this.changeState(STATES.IDLE);
                }
            }

            receiveHit(attackData, attacker) {
                // Determine if blocking
                const isHoldingBack = this.isP1
                    ? (this.opponent.sprite.x > this.sprite.x ? this.scene.p1Keys.left.isDown : this.scene.p1Keys.right.isDown)
                    : (this.opponent.sprite.x > this.sprite.x ? this.scene.p2Keys.left.isDown : this.scene.p2Keys.right.isDown);

                const isCrouching = this.currentState === STATES.CROUCH;
                const successfulBlock = isHoldingBack && (attackData.isHigh ? !isCrouching : isCrouching);

                // Pushback direction
                const pushDir = this.sprite.x < attacker.sprite.x ? -1 : 1;
                this.sprite.setVelocityX(attackData.pushback * pushDir);

                if (successfulBlock) {
                    LOG(`${this.key} BLOCKED attack.`);
                    this.changeState(STATES.BLOCKSTUN);
                    this.stateTimer = attackData.blockstun;
                    this.sprite.setTint(0x00aaff);
                    this.takeDamage(attackData.damage * 0.1); // Chip damage
                } else {
                    LOG(`${this.key} HIT by attack! Dmg: ${attackData.damage}`);
                    this.changeState(STATES.HITSTUN);
                    this.stateTimer = attackData.hitstun;
                    this.sprite.setTint(0xff0000);
                    this.takeDamage(attackData.damage);

                    // Combo tracking
                    attacker.comboCount++;
                    this.scene.updateComboUI(attacker.isP1 ? 'p1' : 'p2', attacker.comboCount);
                }
            }

            processStun() {
                this.stateTimer--;
                if (this.stateTimer <= 0) {
                    this.sprite.clearTint();
                    this.changeState(STATES.IDLE);
                    this.comboCount = 0; // Reset opponent's combo count if we recover
                    this.scene.hideComboUI(this.isP1 ? 'p2' : 'p1');
                }
            }

            takeDamage(amount) {
                this.health -= amount;
                if (this.health <= 0) {
                    this.health = 0;
                    this.changeState(STATES.KO);
                    this.sprite.setTint(0x333333);
                    this.sprite.angle = -90; // Fall over
                    this.scene.handleGameOver(this.isP1 ? 'P2' : 'P1');
                }
                this.scene.updateHealthUI(this.isP1 ? 'p1' : 'p2', this.health, this.maxHealth);
            }

            changeState(newState) {
                if (this.currentState !== newState) {
                    this.currentState = newState;
                    this.stateTimer = 0;
                }
            }

            faceOpponent() {
                if (!this.opponent || this.currentState === STATES.KO) return;
                // Flip sprite based on relative position
                const facingRight = this.sprite.x < this.opponent.sprite.x;
                this.sprite.setFlipX(!facingRight);
            }

            updateHitboxPosition() {
                const facingRight = !this.sprite.flipX;
                this.hitbox.x = facingRight ? this.sprite.x + 60 : this.sprite.x - 60;
                this.hitbox.y = this.sprite.y - 20;
            }
        }

        // --- MAIN SCENE ---
        class FightScene extends Phaser.Scene {
            constructor() {
                super('FightScene');
                this.gameTimer = 99;
                this.timerEvent = null;
            }

            preload() {
                // Generate dynamic placeholders
                let g = this.add.graphics();
                g.fillStyle(0xcc0000); g.fillRect(0, 0, 80, 180); g.generateTexture('p1_tex', 80, 180); g.clear();
                g.fillStyle(0x0066cc); g.fillRect(0, 0, 80, 180); g.generateTexture('p2_tex', 80, 180); g.clear();
                g.fillStyle(0xffffff, 0.8); g.fillRect(0, 0, 80, 30); g.generateTexture('hitbox_tex', 80, 30); g.destroy();
            }

            create() {
                LOG("Initializing Main Fight Scene (1280x720)");
                this.physics.world.setBounds(0, 0, GAME_WIDTH, GAME_HEIGHT);

                // Stage Floor
                this.ground = this.add.rectangle(GAME_WIDTH/2, GROUND_Y + 25, GAME_WIDTH, 50, 0x222222);
                this.physics.add.existing(this.ground, true);

                // Initialize Fighters
                this.player1 = new Fighter(this, 300, GROUND_Y - 90, 'p1_tex', true);
                this.player2 = new Fighter(this, GAME_WIDTH - 300, GROUND_Y - 90, 'p2_tex', false);

                this.player1.setOpponent(this.player2);
                this.player2.setOpponent(this.player1);

                // Collisions
                this.physics.add.collider(this.player1.sprite, this.ground);
                this.physics.add.collider(this.player2.sprite, this.ground);
                this.physics.add.collider(this.player1.sprite, this.player2.sprite); // Pushbox collision

                // Inputs
                this.p1Keys = this.input.keyboard.addKeys({
                    up: Phaser.Input.Keyboard.KeyCodes.W, down: Phaser.Input.Keyboard.KeyCodes.S,
                    left: Phaser.Input.Keyboard.KeyCodes.A, right: Phaser.Input.Keyboard.KeyCodes.D,
                    lightPunch: Phaser.Input.Keyboard.KeyCodes.F, heavyPunch: Phaser.Input.Keyboard.KeyCodes.G
                });

                this.p2Keys = this.input.keyboard.addKeys({
                    up: Phaser.Input.Keyboard.KeyCodes.UP, down: Phaser.Input.Keyboard.KeyCodes.DOWN,
                    left: Phaser.Input.Keyboard.KeyCodes.LEFT, right: Phaser.Input.Keyboard.KeyCodes.RIGHT,
                    lightPunch: Phaser.Input.Keyboard.KeyCodes.NUMPAD_1, heavyPunch: Phaser.Input.Keyboard.KeyCodes.NUMPAD_2
                });

                // Match Timer
                this.timerEvent = this.time.addEvent({ delay: 1000, callback: this.tickTimer, callbackScope: this, loop: true });
            }

            update() {
                this.player1.update(this.p1Keys);
                this.player2.update(this.p2Keys);
            }

            tickTimer() {
                if (this.gameTimer > 0) {
                    this.gameTimer--;
                    document.getElementById('timer').innerText = this.gameTimer;
                    if (this.gameTimer === 0) this.handleTimeOut();
                }
            }

            updateHealthUI(playerKey, current, max) {
                const pct = Math.max(0, (current / max) * 100);
                document.getElementById(`${playerKey}-health`).style.width = `${pct}%`;
            }

            updateComboUI(playerKey, count) {
                if (count > 1) {
                    const el = document.getElementById(`${playerKey}-combo`);
                    el.innerText = `${count} HIT COMBO`;
                    el.style.opacity = 1;

                    // Minor screen shake on combo hits
                    this.cameras.main.shake(100, 0.005);
                }
            }

            hideComboUI(playerKey) {
                document.getElementById(`${playerKey}-combo`).style.opacity = 0;
            }

            handleGameOver(winner) {
                LOG(`MATCH OVER. WINNER: ${winner}`);
                this.timerEvent.remove();
                this.add.text(GAME_WIDTH/2, GAME_HEIGHT/2, `${winner} WINS`, { fontSize: '80px', fontFamily: 'monospace', color: '#ffeb3b', stroke: '#f44336', strokeThickness: 8 }).setOrigin(0.5);
                this.time.delayedCall(3000, () => location.reload()); // Auto reset
            }

            handleTimeOut() {
                LOG("TIME OVER");
                this.timerEvent.remove();
                const p1h = this.player1.health;
                const p2h = this.player2.health;
                let winner = "DRAW";
                if (p1h > p2h) winner = "P1 WINS";
                else if (p2h > p1h) winner = "P2 WINS";

                this.add.text(GAME_WIDTH/2, GAME_HEIGHT/2, `TIME OVER\n${winner}`, { fontSize: '80px', fontFamily: 'monospace', color: '#fff', align: 'center', stroke: '#000', strokeThickness: 8 }).setOrigin(0.5);
                this.player1.changeState(STATES.KO);
                this.player2.changeState(STATES.KO);
            }
        }

        // --- INIT ---
        const config = {
            type: Phaser.AUTO,
            parent: 'game-container',
            width: GAME_WIDTH,
            height: GAME_HEIGHT,
            backgroundColor: '#1a1a1a',
            physics: { default: 'arcade', arcade: { gravity: { y: GRAVITY }, debug: false } },
            scene: FightScene
        };

        const game = new Phaser.Game(config);
    </script>
</body>
</html>