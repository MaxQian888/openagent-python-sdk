const FONTS = {
  heading: "Trebuchet MS",
  body: "Arial"
};

function makeShadow(opacity = 0.18, blur = 5, offset = 2, angle = 45) {
  return {
    type: "outer",
    color: "000000",
    blur,
    offset,
    angle,
    opacity
  };
}

function addAuroraBackground(slide, pres, theme, options = {}) {
  const variant = options.variant || "default";
  slide.background = { color: theme.bg };

  slide.addShape(pres.shapes.RECTANGLE, {
    x: 0,
    y: 0,
    w: 10,
    h: 5.625,
    fill: { color: theme.bg },
    line: { color: theme.bg }
  });

  slide.addShape(pres.shapes.OVAL, {
    x: -1.2,
    y: -0.9,
    w: 4.8,
    h: 3.1,
    fill: { color: theme.accent, transparency: 72 },
    line: { color: theme.accent, transparency: 100 }
  });

  slide.addShape(pres.shapes.OVAL, {
    x: 6.35,
    y: -0.7,
    w: 3.4,
    h: 2.4,
    fill: { color: theme.light, transparency: 91 },
    line: { color: theme.light, transparency: 100 }
  });

  slide.addShape(pres.shapes.OVAL, {
    x: 6.0,
    y: 3.65,
    w: 4.2,
    h: 2.6,
    fill: { color: theme.secondary, transparency: 80 },
    line: { color: theme.secondary, transparency: 100 }
  });

  if (variant === "hero") {
    slide.addShape(pres.shapes.LINE, {
      x: 0.58,
      y: 0.48,
      w: 8.55,
      h: 0,
      line: { color: theme.light, transparency: 82, width: 1 }
    });
  }

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 7.75,
    y: 4.8,
    w: 1.4,
    h: 0.22,
    rectRadius: 0.08,
    fill: { color: theme.accent, transparency: 12 },
    line: { color: theme.accent, transparency: 65, width: 1 }
  });
}

function addEyebrow(slide, theme, text, x, y, w) {
  slide.addText(text.toUpperCase(), {
    x,
    y,
    w,
    h: 0.18,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 9,
    charSpacing: 3,
    color: theme.accent,
    bold: true
  });
}

function addSectionHeader(slide, theme, options) {
  addEyebrow(slide, theme, options.eyebrow, options.x, options.y, options.w || 2.5);

  slide.addText(options.title, {
    x: options.x,
    y: options.y + 0.22,
    w: options.w || 5.2,
    h: options.h || 0.62,
    margin: 0,
    fontFace: FONTS.heading,
    fontSize: options.titleSize || 24,
    bold: true,
    color: options.titleColor || theme.light
  });

  if (options.subtitle) {
    slide.addText(options.subtitle, {
      x: options.x,
      y: options.y + (options.subtitleOffset || 0.92),
      w: options.subtitleW || 4.9,
      h: 0.36,
      margin: 0,
      fontFace: FONTS.body,
      fontSize: options.subtitleSize || 11,
      color: options.subtitleColor || theme.light
    });
  }
}

function addGlassCard(slide, pres, theme, options) {
  const tagY = options.tagY == null ? 0.16 : options.tagY;
  const tagH = options.tagH == null ? 0.12 : options.tagH;
  const titleY =
    options.titleY == null ? (options.tag ? 0.36 : 0.22) : options.titleY;
  const titleH =
    options.titleH == null ? (options.h <= 1.2 ? 0.24 : 0.3) : options.titleH;
  const bodyY =
    options.bodyY == null ? titleY + titleH + 0.12 : options.bodyY;
  const bodyH =
    options.bodyH == null
      ? Math.max(0.16, options.h - bodyY - 0.16)
      : options.bodyH;

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: options.x,
    y: options.y,
    w: options.w,
    h: options.h,
    rectRadius: options.radius || 0.14,
    fill: {
      color: options.fillColor || theme.primary,
      transparency: options.fillTransparency == null ? 36 : options.fillTransparency
    },
    line: {
      color: options.borderColor || theme.light,
      transparency: options.borderTransparency == null ? 76 : options.borderTransparency,
      width: options.borderWidth || 1
    },
    shadow: makeShadow(options.shadowOpacity || 0.18, options.shadowBlur || 4, options.shadowOffset || 2, 45)
  });

  if (options.tag) {
    slide.addText(options.tag, {
      x: options.x + 0.18,
      y: options.y + tagY,
      w: 1.2,
      h: tagH,
      margin: 0,
      fontFace: FONTS.body,
      fontSize: 9,
      charSpacing: 2,
      bold: true,
      color: options.tagColor || theme.accent
    });
  }

  if (options.title) {
    slide.addText(options.title, {
      x: options.x + 0.18,
      y: options.y + titleY,
      w: options.titleW || options.w - 0.36,
      h: titleH,
      margin: 0,
      fontFace: FONTS.heading,
      fontSize: options.titleSize || 15,
      bold: true,
      color: options.titleColor || theme.light,
      fit: "shrink"
    });
  }

  if (options.body) {
    slide.addText(options.body, {
      x: options.x + 0.18,
      y: options.y + bodyY,
      w: options.bodyW || options.w - 0.36,
      h: bodyH,
      margin: 0,
      fontFace: FONTS.body,
      fontSize: options.bodySize || 10.5,
      color: options.bodyColor || theme.light,
      fit: "shrink"
    });
  }
}

function addMetricChip(slide, pres, theme, options) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: options.x,
    y: options.y,
    w: options.w,
    h: options.h || 0.5,
    rectRadius: 0.18,
    fill: { color: options.fillColor || theme.primary, transparency: 24 },
    line: { color: theme.light, transparency: 82, width: 1 }
  });

  slide.addText(options.label, {
    x: options.x + 0.16,
    y: options.y + 0.12,
    w: options.w - 0.32,
    h: 0.15,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 8.5,
    charSpacing: 2,
    color: theme.accent,
    bold: true
  });

  if (options.value) {
    slide.addText(options.value, {
      x: options.x + 0.16,
      y: options.y + 0.23,
      w: options.w - 0.32,
      h: 0.17,
      margin: 0,
      fontFace: FONTS.heading,
      fontSize: 13,
      bold: true,
      color: theme.light,
      align: "right"
    });
  }
}

function addPageBadge(slide, pres, theme, value) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: 9.08,
    y: 5.05,
    w: 0.62,
    h: 0.34,
    rectRadius: 0.15,
    fill: { color: theme.accent, transparency: 6 },
    line: { color: theme.accent, transparency: 28, width: 1 }
  });

  slide.addText(String(value).padStart(2, "0"), {
    x: 9.08,
    y: 5.05,
    w: 0.62,
    h: 0.34,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 10.5,
    bold: true,
    align: "center",
    valign: "middle",
    color: theme.bg
  });
}

function addBarRow(slide, pres, theme, options) {
  slide.addText(options.label, {
    x: options.x,
    y: options.y,
    w: 1.8,
    h: 0.18,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 10,
    color: theme.light,
    bold: true
  });

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: options.x,
    y: options.y + 0.24,
    w: options.w,
    h: 0.2,
    rectRadius: 0.08,
    fill: { color: theme.primary, transparency: 6 },
    line: { color: theme.light, transparency: 92, width: 1 }
  });

  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: options.x,
    y: options.y + 0.24,
    w: Math.max(0.2, options.w * options.ratio),
    h: 0.2,
    rectRadius: 0.08,
    fill: { color: options.color || theme.accent, transparency: 8 },
    line: { color: options.color || theme.accent, transparency: 65, width: 1 }
  });

  slide.addText(options.value, {
    x: options.x + options.w + 0.16,
    y: options.y + 0.18,
    w: 0.52,
    h: 0.18,
    margin: 0,
    fontFace: FONTS.heading,
    fontSize: 12,
    bold: true,
    color: theme.light
  });
}

function addFlowNode(slide, pres, theme, options) {
  addGlassCard(slide, pres, theme, {
    x: options.x,
    y: options.y,
    w: options.w,
    h: options.h,
    tag: options.tag,
    title: options.title,
    body: options.body,
    titleSize: options.titleSize || 13,
    bodySize: options.bodySize || 9.5,
    fillTransparency: options.fillTransparency == null ? 32 : options.fillTransparency
  });
}

function addConnector(slide, pres, theme, fromX, fromY, toX, toY) {
  slide.addShape(pres.shapes.LINE, {
    x: fromX,
    y: fromY,
    w: toX - fromX,
    h: toY - fromY,
    line: { color: theme.accent, transparency: 45, width: 1.5 }
  });
}

function addComparisonRow(slide, pres, theme, options) {
  slide.addShape(pres.shapes.ROUNDED_RECTANGLE, {
    x: options.x,
    y: options.y,
    w: options.w,
    h: 0.48,
    rectRadius: 0.08,
    fill: { color: theme.primary, transparency: 24 },
    line: { color: theme.light, transparency: 88, width: 1 }
  });

  slide.addText(options.label, {
    x: options.x + 0.14,
    y: options.y + 0.14,
    w: 1.45,
    h: 0.16,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 9.5,
    bold: true,
    color: theme.accent
  });

  slide.addText(options.oldValue, {
    x: options.x + 1.75,
    y: options.y + 0.13,
    w: 2.4,
    h: 0.18,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 10.5,
    color: theme.light
  });

  slide.addText(options.newValue, {
    x: options.x + 4.45,
    y: options.y + 0.13,
    w: 2.55,
    h: 0.18,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 10.5,
    bold: true,
    color: theme.light
  });
}

function addFooterCaption(slide, theme, text) {
  slide.addText(text, {
    x: 0.7,
    y: 5.1,
    w: 5.8,
    h: 0.15,
    margin: 0,
    fontFace: FONTS.body,
    fontSize: 8.5,
    color: theme.light
  });
}

module.exports = {
  FONTS,
  addAuroraBackground,
  addBarRow,
  addComparisonRow,
  addConnector,
  addEyebrow,
  addFlowNode,
  addFooterCaption,
  addGlassCard,
  addMetricChip,
  addPageBadge,
  addSectionHeader
};
