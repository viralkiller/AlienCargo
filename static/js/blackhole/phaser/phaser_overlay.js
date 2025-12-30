export function initOverlay(ship) {
  let marker, box, gameOverText, reasonText, shipSprite;
  let sceneContext;

  const game = new Phaser.Game({
    type: Phaser.WEBGL,
    parent: "phaserMount",
    width: innerWidth,
    height: innerHeight,
    transparent: true,
    scale: { mode: Phaser.Scale.RESIZE },
    scene: {
      preload() {
        // [NEW] Load Ship Assets
        this.load.image('ship_off', '/static/png/ship_off.png');
        this.load.image('ship_burners', '/static/png/ship_burners.png');
      },
      create() {
        sceneContext = this;

        // [NEW] The 2.5D Ship Sprite
        // Centered anchor (0.5) is default
        shipSprite = this.add.sprite(0, 0, 'ship_off').setDepth(5);
        // Adjust scale if your PNGs are huge. Start at 0.5 or 1.0.
        shipSprite.setScale(0.5);

        // --- HUD ---
        marker = this.add.circle(0, 0, 5, 0xffffff).setDepth(10);
        marker.setVisible(false); // Hide debug marker now that we have a sprite

        box = this.add.graphics().setDepth(9);
        this.add.text(
          14, 12,
          "Arrow keys: Move\nUp: Boost\nDown: Brake",
          { fontSize: "14px", color: "#fff", stroke: "#000", strokeThickness: 2 }
        ).setDepth(10);

        // --- Game Over Screens ---
        gameOverText = this.add.text(innerWidth / 2, innerHeight / 2 - 20, "GAME OVER", {
          fontSize: "64px",
          color: "#ff3333",
          fontStyle: "bold",
          stroke: "#000",
          strokeThickness: 6
        }).setOrigin(0.5).setVisible(false).setDepth(20);

        reasonText = this.add.text(innerWidth / 2, innerHeight / 2 + 40, "", {
          fontSize: "24px",
          color: "#ffffff",
          stroke: "#000",
          strokeThickness: 4
        }).setOrigin(0.5).setVisible(false).setDepth(20);

        // --- EXPORTS ---
        game.showGameOver = (reason) => {
          shipSprite.setVisible(false); // Hide ship on death
          box.setVisible(false);
          gameOverText.setVisible(true);
          reasonText.setText(reason + "\nPress ENTER to Restart").setVisible(true);
          this.tweens.add({
            targets: [gameOverText, reasonText],
            scale: { from: 0.8, to: 1 },
            duration: 800,
            ease: 'Bounce.Out'
          });
        };

        // [NEW] Sync function for Main Loop
        game.updateShipVisuals = (x, y, isBurnerOn) => {
            if (!shipSprite) return;
            shipSprite.setPosition(x, y);

            // Texture Swap
            const textureKey = isBurnerOn ? 'ship_burners' : 'ship_off';
            if (shipSprite.texture.key !== textureKey) {
                shipSprite.setTexture(textureKey);
            }
        };

        console.log("[PHASER] overlay ready");
      },
      update() {
        if (gameOverText.visible) return;

        // Red Box Draw
        const w = window.innerWidth;
        const h = window.innerHeight;
        const cx = w / 2;
        const by = h - ship.state.boxBottom;

        box.clear().lineStyle(2, 0xff0000, 0.6).strokeRect(
          cx - ship.state.boxWidth / 2,
          by - ship.state.boxHeight,
          ship.state.boxWidth,
          ship.state.boxHeight
        );
      }
    }
  });

  return game;
}