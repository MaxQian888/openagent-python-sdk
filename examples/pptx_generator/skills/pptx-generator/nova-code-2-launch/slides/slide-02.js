const deck = require("./data");
const {
  addAuroraBackground,
  addSectionHeader,
  addGlassCard,
  addPageBadge,
  addFooterCaption
} = require("./helpers");

const slideConfig = {
  type: "thesis",
  index: 2,
  title: "Release Thesis"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme);

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Release thesis",
    title: "What changed in 2.0",
    subtitle: "This release is less about adding isolated tricks and more about changing how the assistant participates in delivery.",
    subtitleW: 5.6,
    h: 0.72,
    subtitleOffset: 1.02
  });

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.72,
    y: 2.08,
    w: 8.48,
    h: 1.04,
    rectRadius: 0.22,
    fill: { color: theme.primary, transparency: 18 },
    line: { color: theme.light, transparency: 82, width: 1 }
  });

  slide.addText("Nova Code 2.0 turns an AI coding assistant into a delivery layer that can frame work, compose the result, and prove it before the team handoff.", {
    x: 1.02,
    y: 2.3,
    w: 7.9,
    h: 0.64,
    margin: 0,
    fontFace: "Trebuchet MS",
    fontSize: 19,
    bold: true,
    color: theme.light,
    align: "center"
  });

  deck.releasePillars.forEach((pillar, index) => {
    addGlassCard(slide, pres, theme, {
      x: 0.74 + index * 2.95,
      y: 3.45,
      w: 2.55,
      h: 1.32,
      tag: pillar.tag,
      title: pillar.title,
      body: pillar.body,
      titleSize: 14,
      bodySize: 10
    });
  });

  addFooterCaption(slide, theme, "The launch story should feel like a product release, not a changelog.");
  addPageBadge(slide, pres, theme, 2);
  return slide;
}

module.exports = { createSlide, slideConfig };
