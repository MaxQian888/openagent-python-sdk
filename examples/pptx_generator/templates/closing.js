// examples/pptx_generator/templates/closing.js
function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  slide.addText(slots.title, {
    x: 0.5, y: 2.0, w: 9, h: 1.0,
    fontSize: 44, fontFace: "Arial",
    color: theme.primary, bold: true, align: "center",
  });
  if (slots.call_to_action) {
    slide.addText(slots.call_to_action, {
      x: 0.5, y: 3.2, w: 9, h: 0.7,
      fontSize: 22, fontFace: "Arial",
      color: theme.accent, align: "center",
    });
  }
  if (slots.contact) {
    slide.addText(slots.contact, {
      x: 0.5, y: 4.2, w: 9, h: 0.5,
      fontSize: 14, fontFace: "Arial",
      color: theme.secondary, align: "center",
    });
  }
  return slide;
}

module.exports = { createSlide };
