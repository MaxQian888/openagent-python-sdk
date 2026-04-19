// examples/pptx_generator/templates/cover.js
function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };

  slide.addText(slots.title, {
    x: 0.5, y: 2, w: 9, h: 1.2,
    fontSize: 48, fontFace: "Arial",
    color: theme.primary, bold: true, align: "center",
  });

  if (slots.subtitle) {
    slide.addText(slots.subtitle, {
      x: 0.5, y: 3.2, w: 9, h: 0.6,
      fontSize: 20, fontFace: "Arial",
      color: theme.secondary, align: "center",
    });
  }

  if (slots.author || slots.date) {
    slide.addText(`${slots.author || ""}  ${slots.date || ""}`.trim(), {
      x: 0.5, y: 4.8, w: 9, h: 0.35,
      fontSize: 12, fontFace: "Arial",
      color: theme.accent, align: "center",
    });
  }

  return slide;
}

module.exports = { createSlide };
