export function initOverlay(ship) {
  let marker, box, gameOverText, reasonText;

  const game = new Phaser.Game({
    type: Phaser.WEBGL,
    parent: "phaserMount",
    width: innerWidth,
    height: innerHeight,
    transparent: true, // Crucial for overlay
    scale: { mode: Phaser.Scale.RESIZE },
    scene: {
      create() {
        // --- HUD ---
        marker = this.add.circle(0, 0, 5, 0xffffff).setDepth(10);
        box = this.add.graphics().setDepth(9);

        this.add.text(
          14, 12,
          "Arrow keys: ship (bottom box)\nAvoid orbiting asteroids\nAvoid Planets",
          { fontSize: "14px", color: "#fff", stroke: "#000", strokeThickness: 2 }
        );

        // --- Game Over Screens (Hidden by default) ---
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

        // --- Expose function to Main Loop ---
        game.showGameOver = (reason) => {
          marker.setVisible(false);
          box.setVisible(false);

          gameOverText.setVisible(true);
          reasonText.setText(reason + "\nReload to Restart").setVisible(true);

          // Simple bounce animation
          this.tweens.add({
            targets: [gameOverText, reasonText],
            scale: { from: 0.8, to: 1 },
            duration: 800,
            ease: 'Bounce.Out'
          });
        };

        console.log("[PHASER] overlay ready");
      },

      update() {
        // Don't update HUD if game is over (optional preference)
        if (gameOverText.visible) return;

        const v = ship.mesh.position.clone().project(window.__camera);
        const w = window.innerWidth;
        const h = window.innerHeight;

        marker.setPosition((v.x * 0.5 + 0.5) * w, (-v.y * 0.5 + 0.5) * h);

        const cx = w / 2;
        const by = h - ship.state.boxBottom;

        // Red Control Box
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