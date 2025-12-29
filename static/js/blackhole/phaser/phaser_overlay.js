export function initOverlay(ship) {
  let marker, box;

  const game = new Phaser.Game({
    type: Phaser.WEBGL,
    parent: "phaserMount",
    width: innerWidth,
    height: innerHeight,
    transparent: true,
    scale: { mode: Phaser.Scale.RESIZE },
    scene: {
      create() {
        marker = this.add.circle(0, 0, 5, 0xffffff).setDepth(10);
        box = this.add.graphics().setDepth(9);

        this.add.text(
          14, 12,
          "Arrow keys: ship (bottom box)\nAvoid orbiting asteroids\nCamera follows ship",
          { fontSize: "14px", color: "#fff" }
        );

        console.log("[PHASER] overlay ready");
      },
      update() {
        const v = ship.mesh.position.clone().project(window.__camera);
        const w = window.innerWidth;
        const h = window.innerHeight;

        marker.setPosition((v.x * 0.5 + 0.5) * w, (-v.y * 0.5 + 0.5) * h);

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
