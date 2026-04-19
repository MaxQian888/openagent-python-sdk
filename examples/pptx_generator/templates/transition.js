// examples/pptx_generator/templates/transition.js
function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.primary };

  slide.addText(String(slots.section_number), {
    x: 0.5, y: 1.6, w: 9, h: 1.5,
    fontSize: 96, fontFace: "Arial",
    color: theme.light, bold: true, align: "center",
  });
  slide.addText(slots.section_title, {
    x: 0.5, y: 3.2, w: 9, h: 1.0,
    fontSize: 36, fontFace: "Arial",
    color: theme.bg, bold: true, align: "center",
  });
  if (slots.subtitle) {
    slide.addText(slots.subtitle, {
      x: 0.5, y: 4.3, w: 9, h: 0.5,
      fontSize: 16, fontFace: "Arial",
      color: theme.light, align: "center",
    });
  }
  return slide;
}

module.exports = { createSlide };
