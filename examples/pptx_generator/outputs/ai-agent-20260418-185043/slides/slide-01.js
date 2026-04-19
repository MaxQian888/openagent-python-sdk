const base = (function() {
  var module = { exports: {} };
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

  return module.exports;
})();
const slots = {"title": "AI Agent 运行时架构：从核心机制到生产实践", "subtitle": "面向技术开发者与架构师的系统性分享", "author": null, "date": null};
function createSlide(pres, theme) { return base.createSlide(pres, theme, slots); }
module.exports = { createSlide };
