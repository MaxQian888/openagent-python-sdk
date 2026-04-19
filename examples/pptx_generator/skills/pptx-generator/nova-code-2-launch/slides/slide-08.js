const deck = require("./data");
const {
  addAuroraBackground,
  addSectionHeader,
  addComparisonRow,
  addPageBadge
} = require("./helpers");

const slideConfig = {
  type: "comparison",
  index: 8,
  title: "1.x vs 2.0"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme);

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Version comparison",
    title: "1.x vs 2.0: the product-team shift",
    subtitle: "The difference is not one feature. The difference is the default shape of the work.",
    subtitleW: 5.4,
    w: 6.2,
    h: 0.78,
    titleSize: 22,
    subtitleOffset: 0.96
  });

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 0.72,
    y: 1.94,
    w: 8.45,
    h: 0.5,
    rectRadius: 0.08,
    fill: { color: theme.primary, transparency: 22 },
    line: { color: theme.light, transparency: 88, width: 1 }
  });

  slide.addText("DIMENSION", {
    x: 0.86,
    y: 2.12,
    w: 1.0,
    h: 0.16,
    margin: 0,
    fontFace: "Arial",
    fontSize: 9,
    charSpacing: 2,
    bold: true,
    color: theme.accent
  });

  slide.addText("1.x", {
    x: 2.47,
    y: 2.12,
    w: 0.8,
    h: 0.16,
    margin: 0,
    fontFace: "Trebuchet MS",
    fontSize: 11,
    bold: true,
    color: theme.light
  });

  slide.addText("2.0", {
    x: 5.2,
    y: 2.12,
    w: 1.2,
    h: 0.16,
    margin: 0,
    fontFace: "Trebuchet MS",
    fontSize: 11,
    bold: true,
    color: theme.light
  });

  deck.comparisonRows.forEach((row, index) => {
    addComparisonRow(slide, pres, theme, {
      x: 0.72,
      y: 2.6 + index * 0.56,
      w: 8.45,
      label: row.label,
      oldValue: row.oldValue,
      newValue: row.newValue
    });
  });

  addPageBadge(slide, pres, theme, 8);
  return slide;
}

module.exports = { createSlide, slideConfig };
