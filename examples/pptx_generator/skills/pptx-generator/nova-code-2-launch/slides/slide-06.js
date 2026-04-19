const deck = require("./data");
const {
  addAuroraBackground,
  addSectionHeader,
  addPageBadge
} = require("./helpers");

const slideConfig = {
  type: "capability",
  index: 6,
  title: "Context continuity"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme);

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Capability 03",
    title: "Context continuity across the release thread",
    subtitle: "The output improves when the session remembers intent, repo truth, and verification state at the same time.",
    subtitleW: 5.4
  });

  deck.continuityLayers.forEach((layer, index) => {
    slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
      x: 0.88,
      y: 1.98 + index * 0.72,
      w: 4.5,
      h: 0.54,
      rectRadius: 0.16,
      fill: { color: theme.primary, transparency: 18 + index * 8 },
      line: { color: theme.light, transparency: 82, width: 1 }
    });

    slide.addText(layer.title, {
      x: 1.14,
      y: 2.16 + index * 0.72,
      w: 1.55,
      h: 0.16,
      margin: 0,
      fontFace: "Trebuchet MS",
      fontSize: 12,
      bold: true,
      color: theme.accent
    });

    slide.addText(layer.body, {
      x: 2.78,
      y: 2.12 + index * 0.72,
      w: 2.25,
      h: 0.2,
      margin: 0,
      fontFace: "Arial",
      fontSize: 9.5,
      color: theme.light
    });
  });

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 5.98,
    y: 2.0,
    w: 3.1,
    h: 2.92,
    rectRadius: 0.16,
    fill: { color: theme.primary, transparency: 28 },
    line: { color: theme.light, transparency: 78, width: 1 }
  });

  slide.addText("TEAM EFFECT", {
    x: 6.18,
    y: 2.22,
    w: 1.2,
    h: 0.16,
    margin: 0,
    fontFace: "Arial",
    fontSize: 9,
    charSpacing: 2,
    bold: true,
    color: theme.accent
  });

  slide.addText("Why continuity matters to the product team", {
    x: 6.18,
    y: 2.52,
    w: 2.3,
    h: 0.26,
    margin: 0,
    fontFace: "Trebuchet MS",
    fontSize: 15,
    bold: true,
    color: theme.light
  });

  slide.addText("Release-quality output depends on more than one prompt.\n\n2.0 keeps the session aligned with the active objective, the actual project constraints, and the current proof state so the final artifact stays coherent.", {
    x: 6.18,
    y: 3.02,
    w: 2.38,
    h: 1.2,
    margin: 0,
    fontFace: "Arial",
    fontSize: 10.3,
    color: theme.light
  });

  addPageBadge(slide, pres, theme, 6);
  return slide;
}

module.exports = { createSlide, slideConfig };
