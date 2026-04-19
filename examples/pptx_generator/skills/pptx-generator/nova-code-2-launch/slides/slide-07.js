const deck = require("./data");
const {
  addAuroraBackground,
  addSectionHeader,
  addFlowNode,
  addConnector,
  addGlassCard,
  addPageBadge
} = require("./helpers");

const slideConfig = {
  type: "workflow",
  index: 7,
  title: "Workflow upgrade"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme);

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Workflow upgrade",
    title: "The release path is now visible end to end",
    subtitle: "This is the operating rhythm the product team is expected to feel in 2.0.",
    subtitleW: 4.8
  });

  deck.workflowSteps.forEach((step, index) => {
    const x = 0.78 + index * 1.8;
    addFlowNode(slide, pres, theme, {
      x,
      y: 2.1,
      w: 1.52,
      h: 1.5,
      tag: step.tag,
      title: step.title,
      body: step.body,
      titleSize: 13,
      bodySize: 9.4
    });

    if (index < deck.workflowSteps.length - 1) {
      addConnector(slide, pres, theme, x + 1.52, 2.86, x + 1.8, 2.86);
    }
  });

  addGlassCard(slide, pres, theme, {
    x: 1.08,
    y: 4.15,
    w: 7.85,
    h: 0.78,
    tag: "WHAT IMPROVES",
    title: "Requests become shaped release work instead of floating prompt fragments.",
    titleSize: 14,
    titleY: 0.3,
    body: ""
  });

  addPageBadge(slide, pres, theme, 7);
  return slide;
}

module.exports = { createSlide, slideConfig };
