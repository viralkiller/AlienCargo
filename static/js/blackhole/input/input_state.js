export const input = {
  keys: new Set(),
  dragging: false,
  yaw: 0,
  pitch: 0
};

window.addEventListener("keydown", e => input.keys.add(e.code));
window.addEventListener("keyup", e => input.keys.delete(e.code));
