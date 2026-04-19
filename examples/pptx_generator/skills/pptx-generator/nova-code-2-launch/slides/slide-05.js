const deck = require("./data");
const {
  addAuroraBackground,
  addSectionHeader,
  addGlassCard,
  addBarRow,
  addPageBadge,
  addMetricChip
} = require("./helpers");

const slideConfig = {
  type: "capability",
  index: 5,
  title: "Verification loop"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme);

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Capability 02",
    title: "Verification is part of the product surface",
    subtitle: "2.0 closes the loop by making proof visible before the result leaves the session.",
    subtitleW: 5.0
  });

  addMetricChip(slide, pres, theme, {
    x: 7.02,
    y: 0.82,
    w: 1.86,
    label: "Issue surfacing",
    value: "3.2x"
  });

  addGlassCard(slide, pres, theme, {
    x: 0.72,
    y: 2.28,
    w: 3.0,
    h: 2.0,
    tag: "RELEASE EFFECT",
    title: "Quality signals move earlier in the flow",
    body: "Instead of waiting for a human to ask for proof, the system treats lint, tests, and build outcomes as part of the default release path.",
    titleSize: 15,
    bodySize: 10.4,
    bodyH: 0.95
  });

  addGlassCard(slide, pres, theme, {
    x: 4.1,
    y: 1.88,
    w: 5.0,
    h: 2.54,
    tag: "QUALITY LOOP",
    title: "Signals surfaced in the release lane",
    titleY: 0.54,
    titleH: 0.26,
    body: ""
  });

  deck.verificationBars.forEach((bar, index) => {
    addBarRow(slide, pres, theme, {
      x: 4.38,
      y: 2.66 + index * 0.58,
      w: 3.55,
      label: bar.label,
      ratio: bar.ratio,
      value: bar.value,
      color: bar.color
    });
  });

  slide.addText("The objective is not to run every possible check. The objective is to give the team enough proof to trust the handoff.", {
    x: 4.38,
    y: 4.72,
    w: 4.2,
    h: 0.28,
    margin: 0,
    fontFace: "Arial",
    fontSize: 10,
    color: theme.light
  });

  addPageBadge(slide, pres, theme, 5);
  return slide;
}

module.exports = { createSlide, slideConfig };
