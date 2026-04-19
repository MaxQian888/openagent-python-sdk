const fs = require("node:fs");
const path = require("node:path");
const pptxgen = require("pptxgenjs");
const deck = require("./data");

const slideModules = [
  require("./slide-01"),
  require("./slide-02"),
  require("./slide-03"),
  require("./slide-04"),
  require("./slide-05"),
  require("./slide-06"),
  require("./slide-07"),
  require("./slide-08"),
  require("./slide-09"),
  require("./slide-10")
];

async function main() {
  const outputDir = path.join(__dirname, "output");
  fs.mkdirSync(outputDir, { recursive: true });

  const pres = new pptxgen();
  pres.layout = "LAYOUT_16x9";
  pres.author = "Codex";
  pres.company = "skills-test";
  pres.subject = "Nova Code 2.0 launch deck";
  pres.title = `${deck.product} - ${deck.subtitle}`;

  for (const slideModule of slideModules) {
    slideModule.createSlide(pres, deck.theme);
  }

  const outputFile =
    process.env.PPTX_OUT || path.join(outputDir, "nova-code-2-launch.pptx");
  await pres.writeFile({ fileName: outputFile });
  console.log(outputFile);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
