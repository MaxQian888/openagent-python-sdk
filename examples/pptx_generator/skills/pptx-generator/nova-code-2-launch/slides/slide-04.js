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
  type: "capability",
  index: 4,
  title: "Spec-to-code orchestration"
};

function createSlide(pres, theme) {
  const slide = pres.addSlide();
  addAuroraBackground(slide, pres, theme);

  addSectionHeader(slide, theme, {
    x: 0.72,
    y: 0.56,
    eyebrow: "Capability 01",
    title: "Spec-to-code orchestration",
    subtitle: "2.0 starts by shaping the work before it starts writing output.",
    subtitleW: 4.8
  });

  addGlassCard(slide, pres, theme, {
    x: 0.72,
    y: 1.86,
    w: 3.0,
    h: 2.86,
    tag: "WHY IT MATTERS",
    title: "The team gets a path, not just a patch",
    body: "Nova Code 2.0 frames the request, identifies the output surface, and keeps the final artifact aligned with the release objective.\n\nInputs stay tied to deliverables instead of disappearing into one-off prompt history.",
    titleSize: 16,
    bodySize: 10.6,
    bodyY: 0.84,
    bodyH: 1.72
  });

  addGlassCard(slide, pres, theme, {
    x: 0.86,
    y: 4.78,
    w: 2.6,
    h: 0.48,
    tag: "WORK UNIT",
    title: "Request -> plan -> module -> proof",
    titleSize: 11,
    tagY: 0.08,
    tagH: 0.1,
    titleY: 0.22,
    titleH: 0.15,
    body: ""
  });

  const nodes = deck.orchestrationSteps;
  addFlowNode(slide, pres, theme, { x: 4.15, y: 1.88, w: 2.1, h: 1.04, tag: nodes[0].tag, title: nodes[0].title, body: nodes[0].body });
  addFlowNode(slide, pres, theme, { x: 6.55, y: 1.88, w: 2.1, h: 1.04, tag: nodes[1].tag, title: nodes[1].title, body: nodes[1].body });
  addFlowNode(slide, pres, theme, { x: 4.15, y: 3.18, w: 2.1, h: 1.04, tag: nodes[2].tag, title: nodes[2].title, body: nodes[2].body });
  addFlowNode(slide, pres, theme, { x: 6.55, y: 3.18, w: 2.1, h: 1.04, tag: nodes[3].tag, title: nodes[3].title, body: nodes[3].body });

  addConnector(slide, pres, theme, 6.25, 2.4, 6.55, 2.4);
  addConnector(slide, pres, theme, 5.2, 2.92, 5.2, 3.18);
  addConnector(slide, pres, theme, 7.6, 2.92, 7.6, 3.18);

  addPageBadge(slide, pres, theme, 4);
  return slide;
}

module.exports = { createSlide, slideConfig };
