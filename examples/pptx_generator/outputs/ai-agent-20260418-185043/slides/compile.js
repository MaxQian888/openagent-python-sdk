const pptxgen = require("pptxgenjs");

async function main() {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.title = "AI Agent \u8fd0\u884c\u65f6\u67b6\u6784\u7684\u6280\u672f\u5206\u4eab";
  const theme = {"primary": "22223b", "secondary": "4a4e69", "accent": "9a8c98", "light": "c9ada7", "bg": "f2e9e4"};
  require("./slide-01.js").createSlide(pres, theme);
  require("./slide-02.js").createSlide(pres, theme);
  require("./slide-06.js").createSlide(pres, theme);
  await pres.writeFile({ fileName: "./output/presentation.pptx" });
}

main().catch((err) => { console.error(err); process.exitCode = 1; });
