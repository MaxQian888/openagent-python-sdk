// examples/pptx_generator/templates/content.js
function renderBlock(slide, pres, theme, block, y) {
  if (block.kind === "bullets") {
    slide.addText(block.items.map((t) => ({ text: t, options: { bullet: true } })), {
      x: 0.6, y, w: 8.8, h: 3,
      fontSize: 16, fontFace: "Arial", color: theme.primary,
    });
    return y + 3.2;
  }
  if (block.kind === "two_column") {
    const col = (items, x) =>
      slide.addText(items.map((t) => ({ text: t, options: { bullet: true } })), {
        x, y, w: 4.2, h: 3,
        fontSize: 14, fontFace: "Arial", color: theme.primary,
      });
    col(block.left_items, 0.6);
    col(block.right_items, 5.2);
    return y + 3.2;
  }
  if (block.kind === "callout") {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.6, y, w: 8.8, h: 1.0,
      fill: { color: theme.accent }, rectRadius: 0.15,
    });
    slide.addText(block.text, {
      x: 0.8, y, w: 8.4, h: 1.0,
      fontSize: 16, fontFace: "Arial", color: "FFFFFF",
      valign: "middle",
    });
    return y + 1.2;
  }
  return y;
}

function createSlide(pres, theme, slots) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };
  slide.addText(slots.title, {
    x: 0.5, y: 0.4, w: 9, h: 0.7,
    fontSize: 28, fontFace: "Arial",
    color: theme.primary, bold: true,
  });
  let y = 1.3;
  (slots.body_blocks || []).forEach((b) => {
    y = renderBlock(slide, pres, theme, b, y);
  });
  return slide;
}

module.exports = { createSlide };
