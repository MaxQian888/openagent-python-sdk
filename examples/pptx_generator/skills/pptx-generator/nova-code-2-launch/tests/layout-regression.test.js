const test = require("node:test");
const assert = require("node:assert/strict");

const deck = require("../slides/data");
const { addGlassCard } = require("../slides/helpers");
const slide02 = require("../slides/slide-02");
const slide05 = require("../slides/slide-05");
const slide06 = require("../slides/slide-06");

function createRecorder() {
  const records = [];
  const slide = {
    background: null,
    addShape(type, options) {
      records.push({ kind: "shape", type, ...options });
      return slide;
    },
    addText(text, options) {
      const normalized =
        Array.isArray(text)
          ? text
              .map((part) => (typeof part === "string" ? part : part.text || ""))
              .join(" ")
          : text;
      records.push({ kind: "text", text: normalized, ...options });
      return slide;
    }
  };

  const pres = {
    shapes: {
      RECTANGLE: "RECTANGLE",
      OVAL: "OVAL",
      LINE: "LINE",
      ROUNDED_RECTANGLE: "ROUNDED_RECTANGLE"
    },
    addSlide() {
      return slide;
    }
  };

  return { pres, slide, records };
}

function bottom(item) {
  return item.y + item.h;
}

function runSlide(slideModule) {
  const { pres, records } = createRecorder();
  slideModule.createSlide(pres, deck.theme);
  return records;
}

test("glass cards keep tag, title, and body inside short cards", () => {
  const { pres, slide, records } = createRecorder();

  addGlassCard(slide, pres, deck.theme, {
    x: 0.78,
    y: 1.85,
    w: 3.72,
    h: 1.08,
    tag: "01",
    title: "Complex feature build",
    body: "Best when the team needs plan, implementation, and validation in one release thread.",
    titleSize: 15,
    bodySize: 10.2
  });

  const card = records.find((item) => item.kind === "shape" && item.x === 0.78 && item.y === 1.85);
  const textItems = records.filter((item) => item.kind === "text");

  assert.ok(card, "expected card background to be recorded");

  for (const item of textItems) {
    assert.ok(
      bottom(item) <= bottom(card),
      `text overflows card bounds: ${item.text}`
    );
  }
});

test("slide 02 keeps the thesis banner below the subtitle block", () => {
  const records = runSlide(slide02);
  const subtitle = records.find(
    (item) =>
      item.kind === "text" &&
      typeof item.text === "string" &&
      item.text.startsWith("This release is less about adding isolated tricks")
  );
  const banner = records.find(
    (item) =>
      item.kind === "shape" &&
      item.type === "ROUNDED_RECTANGLE" &&
      item.w > 8 &&
      item.y > 1.5
  );

  assert.ok(subtitle, "expected slide subtitle");
  assert.ok(banner, "expected thesis banner");
  assert.ok(bottom(subtitle) + 0.08 <= banner.y, "subtitle overlaps the thesis banner");
});

test("slide 05 keeps the issue chip separate from the release-effect card", () => {
  const records = runSlide(slide05);
  const chip = records.find(
    (item) =>
      item.kind === "shape" &&
      item.type === "ROUNDED_RECTANGLE" &&
      item.w === 1.86 &&
      item.h === 0.5
  );
  const releaseCard = records.find(
    (item) =>
      item.kind === "shape" &&
      item.type === "ROUNDED_RECTANGLE" &&
      item.w === 3.0 &&
      item.h === 2.0
  );

  assert.ok(chip, "expected issue chip");
  assert.ok(releaseCard, "expected release-effect card");
  assert.ok(bottom(chip) + 0.08 <= releaseCard.y, "issue chip overlaps the release-effect card");
});

test("slide 06 continuity layers do not overlap each other", () => {
  const records = runSlide(slide06);
  const layers = records
    .filter(
      (item) =>
        item.kind === "shape" &&
        item.type === "ROUNDED_RECTANGLE" &&
        item.x < 1.2 &&
        item.w > 4 &&
        item.h >= 0.5 &&
        item.h <= 0.8
    )
    .sort((a, b) => a.y - b.y);

  assert.equal(layers.length, 4, "expected four continuity layers");

  for (let index = 1; index < layers.length; index += 1) {
    assert.ok(
      bottom(layers[index - 1]) + 0.08 <= layers[index].y,
      `continuity layers ${index} and ${index + 1} overlap`
    );
  }
});
