const deck = require("./data");
const {
  addAuroraBackground,
  addSectionHeader,
  addGlassCard,
  addPageBadge
} = require("./helpers");

const slideConfig = {
  type: "scenarios",
  index: 9,
  title: "Best-fit scenarios"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme);

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Best-fit scenarios",
    title: "Where Nova Code 2.0 creates the most product-team leverage",
    subtitle: "The release is strongest when the team needs shape, continuity, and proof in the same thread.",
    subtitleW: 5.3
  });

  deck.scenarios.forEach((item, index) => {
    const col = index % 2;
    const row = Math.floor(index / 2);
    addGlassCard(slide, pres, theme, {
      x: 0.78 + col * 4.28,
      y: 2.02 + row * 1.48,
      w: 3.72,
      h: 1.22,
      tag: item.tag,
      title: item.title,
      body: item.body,
      titleSize: 15,
      bodySize: 10.2
    });
  });

  addGlassCard(slide, pres, theme, {
    x: 0.78,
    y: 4.92,
    w: 8.35,
    h: 0.44,
    tag: "NOTE",
    title: "2.0 is not trying to replace judgment. It is trying to make product delivery easier to shape and easier to trust.",
    titleSize: 11,
    tagY: 0.08,
    tagH: 0.1,
    titleY: 0.2,
    titleH: 0.16,
    body: "",
    fillTransparency: 28
  });

  addPageBadge(slide, pres, theme, 9);
  return slide;
}

module.exports = { createSlide, slideConfig };
