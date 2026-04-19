// examples/pptx_generator/templates/agenda.js
function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  slide.addText(slots.title, {
    x: 0.5, y: 0.4, w: 9, h: 0.7,
    fontSize: 32, fontFace: "Arial",
    color: theme.primary, bold: true,
  });

  const items = slots.items || [];
  items.forEach((it, i) => {
    slide.addShape(pres.shapes.OVAL, {
      x: 0.6, y: 1.3 + i * 0.6, w: 0.35, h: 0.35,
      fill: { color: theme.accent },
    });
    slide.addText(String(i + 1), {
      x: 0.6, y: 1.3 + i * 0.6, w: 0.35, h: 0.35,
      fontSize: 12, fontFace: "Arial", color: "FFFFFF",
      bold: true, align: "center", valign: "middle",
    });
    slide.addText(it.label, {
      x: 1.1, y: 1.3 + i * 0.6, w: 7.5, h: 0.35,
      fontSize: 18, fontFace: "Arial", color: theme.primary,
      valign: "middle",
    });
    if (it.sub) {
      slide.addText(it.sub, {
        x: 1.1, y: 1.6 + i * 0.6, w: 7.5, h: 0.25,
        fontSize: 12, fontFace: "Arial", color: theme.secondary,
      });
    }
  });

  return slide;
}

module.exports = { createSlide };
