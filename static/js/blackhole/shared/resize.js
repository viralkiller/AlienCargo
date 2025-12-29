export function setupResize(renderer, camera, phaserGame) {
  let queued = false;

  function doResize() {
    queued = false;
    const w = window.innerWidth;
    const h = window.innerHeight;

    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();

    if (phaserGame?.scale?.resize) {
      try { phaserGame.scale.resize(w, h); }
      catch {}
    }

    console.log("[RESIZE]", w, h);
  }

  window.addEventListener("resize", () => {
    if (queued) return;
    queued = true;
    requestAnimationFrame(doResize);
  });

  doResize();
}
