const deck = require("./data");
const {
  addAuroraBackground,
  addSectionHeader,
  addGlassCard,
  addPageBadge
} = require("./helpers");

const slideConfig = {
  type: "closing",
  index: 10,
  title: "Closing"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme, { variant: "hero" });

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Closing",
    title: "Nova Code 2.0 is a capability release for shipping teams",
    subtitle: "The value is not just faster generation. The value is a better path from request to trusted output.",
    subtitleW: 5.25
  });

  deck.impactMetrics.forEach((metric, index) => {
    addGlassCard(slide, pres, theme, {
      x: 0.78 + index * 2.9,
      y: 2.02,
      w: 2.45,
      h: 1.45,
      tag: metric.label,
      title: metric.value,
      body: metric.body,
      titleSize: 28,
      titleY: 0.36,
      bodyY: 0.88,
      bodySize: 10
    });
  });

  addGlassCard(slide, pres, theme, {
    x: 0.78,
    y: 3.84,
    w: 8.35,
    h: 1.34,
    tag: "NEXT ACTIONS",
    title: "Recommended rollout path",
    body: deck.nextActions.map((item, index) => `${index + 1}. ${item}`).join("\n"),
    titleSize: 14,
    bodySize: 10.2,
    bodyY: 0.62,
    bodyH: 0.56
  });

  addPageBadge(slide, pres, theme, 10);
  return slide;
}

module.exports = { createSlide, slideConfig };
