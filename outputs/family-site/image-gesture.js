const FamilyImageGestures = (() => {
  const ZOOM_SCALE = 2;
  const HORIZONTAL_SWIPE = 55;
  const VERTICAL_DISMISS = 95;
  const EDGE_SWITCH = 60;

  function panLimits(imageWidth, imageHeight, viewportWidth, viewportHeight, scale = ZOOM_SCALE) {
    return {
      x: Math.max(0, (imageWidth * scale - viewportWidth) / 2),
      y: Math.max(0, (imageHeight * scale - viewportHeight) / 2)
    };
  }

  function clamp(value, limit) {
    return Math.min(Math.max(value, -limit), limit);
  }

  function resolveImageGesture({zoomed, pan, delta, limits}) {
    const dx = delta.x;
    const dy = delta.y;
    if (zoomed) {
      if (Math.abs(dy) > Math.abs(dx) * 1.15 && Math.abs(dy) >= VERTICAL_DISMISS) return {action:"close"};
      const x = pan.x + dx;
      const y = pan.y + dy;
      if (Math.abs(dx) >= Math.abs(dy)) {
        if (dx < 0 && x < -limits.x - EDGE_SWITCH) return {action:"next"};
        if (dx > 0 && x > limits.x + EDGE_SWITCH) return {action:"previous"};
      }
      return {action:"pan", pan:{x:clamp(x,limits.x),y:clamp(y,limits.y)}};
    }
    if (Math.abs(dx) > Math.abs(dy) * 1.15 && Math.abs(dx) >= HORIZONTAL_SWIPE) {
      return {action:dx < 0 ? "next" : "previous"};
    }
    if (Math.abs(dy) > Math.abs(dx) * 1.15 && Math.abs(dy) >= VERTICAL_DISMISS) {
      return {action:"close"};
    }
    return {action:"none"};
  }

  return {panLimits, resolveImageGesture};
})();

if (typeof module !== "undefined" && module.exports) module.exports = FamilyImageGestures;
if (typeof window !== "undefined") window.FamilyImageGestures = FamilyImageGestures;
