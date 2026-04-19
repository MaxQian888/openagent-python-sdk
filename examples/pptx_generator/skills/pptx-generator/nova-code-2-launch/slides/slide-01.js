const deck = require("./data");
const {
  addAuroraBackground,
  addGlassCard,
  addMetricChip,
  addEyebrow,
  FONTS
} = require("./helpers");

const slideConfig = {
  type: "cover",
  index: 1,
  title: deck.product
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme, { variant: "hero" });

  addEyebrow(slide, theme, deck.launchLabel, 0.72, 0.58, 2.6);

  slide.addText(deck.product, {
    x: 0.7,
    y: 1.0,
    w: 5.6,
    h: 0.9,
    margin: 0,
    fontFace: FONTS.heading,
    fontSize: 31,
    bold: true,
    color: theme.light
  });

  slide.addText(deck.subtitle, {
    x: 0.72,
    y: 1.88,
    w: 3.6,
    h: 0.28,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 14,
    color: theme.accent,
    bold: true
  });

  slide.addText(deck.releaseThesis, {
    x: 0.72,
    y: 2.36,
    w: 5.15,
    h: 1.0,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 12,
    color: theme.light
  });

  deck.highlightChips.forEach((label, index) => {
    addMetricChip(slide, pres, theme, {
      x: 0.72 + index * 1.72,
      y: 4.15,
      w: 1.56,
      label
    });
  });

  addGlassCard(slide, pres, theme, {
    x: 6.35,
    y: 0.82,
    w: 2.95,
    h: 3.92,
    tag: "RELEASE FOCUS",
    title: "Capability release for product teams",
    body: "Nova Code 2.0 is designed to make internal product delivery feel less like prompt churn and more like a repeatable release surface.",
    titleSize: 17,
    bodySize: 11,
    bodyH: 0.88,
    fillTransparency: 26
  });

  deck.heroMetrics.forEach((metric, index) => {
    addMetricChip(slide, pres, theme, {
      x: 6.58,
      y: 2.78 + index * 0.44,
      w: 2.46,
      label: metric.label,
      value: metric.value
    });
  });

  slide.addText("April 2026", {
    x: 0.74,
    y: 5.02,
    w: 1.1,
    h: 0.16,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 9,
    color: theme.light
  });

  return slide;
}

module.exports = { createSlide, slideConfig };
