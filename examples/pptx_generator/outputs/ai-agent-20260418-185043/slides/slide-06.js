// FREEFORM fallback for slide index=6 reason='schema-retry-exhausted: {"index":6,"type":"content","title":"生产级架构：治理、可观测性与框架生态","subtitle":"从原型到生产的关键跨越'
function createSlide(pres, theme) {
  const slide = pres.addSlide();
  slide.background = { color: theme.bg };
  slide.addText("\u751f\u4ea7\u7ea7\u67b6\u6784\uff1a\u6cbb\u7406\u3001\u53ef\u89c2\u6d4b\u6027\u4e0e\u6846\u67b6\u751f\u6001", { x: 0.5, y: 2.4, w: 9, h: 0.8, fontSize: 32, fontFace: 'Arial', color: theme.primary, bold: true, align: 'center' }});
  return slide;
}
module.exports = { createSlide };
