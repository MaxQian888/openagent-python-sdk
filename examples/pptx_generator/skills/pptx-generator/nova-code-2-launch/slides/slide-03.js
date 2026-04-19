const deck = require("./data");
const {
  addAuroraBackground,
  addSectionHeader,
  addGlassCard,
  addMetricChip,
  addPageBadge
} = require("./helpers");

const slideConfig = {
  type: "overview",
  index: 3,
  title: "Capability Surface"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme);

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Capability surface",
    title: "The 2.0 release is organized around four product surfaces",
    subtitle: "These are the experiences the internal product team will actually feel in day-to-day use.",
    subtitleW: 6.0,
    w: 6.2,
    h: 0.92,
    titleSize: 22,
    subtitleOffset: 1.12
  });

  addMetricChip(slide, pres, theme, {
    x: 7.2,
    y: 0.76,
    w: 1.92,
    label: "Launch scope",
    value: "4 cores"
  });

  deck.capabilities.forEach((item, index) => {
    const col = index % 2;
    const row = Math.floor(index / 2);
    addGlassCard(slide, pres, theme, {
      x: 0.78 + col * 4.28,
      y: 2.12 + row * 1.54,
      w: 3.75,
      h: 1.18,
      tag: item.tag,
      title: item.title,
      body: item.body,
      titleSize: 15,
      bodySize: 10.3
    });
  });

  slide.addText("From here, the deck drills into three release pillars and one team outcome layer.", {
    x: 0.78,
    y: 5.02,
    w: 5.1,
    h: 0.18,
    margin: 0,
    fontFace: "Arial",
    fontSize: 9.5,
    color: theme.light
  });

  addPageBadge(slide, pres, theme, 3);
  return slide;
}

module.exports = { createSlide, slideConfig };
