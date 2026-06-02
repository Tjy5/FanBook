import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import assert from "node:assert/strict";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, "..");
const html = readFileSync(join(frontendRoot, "index.html"), "utf8");
const css = readFileSync(join(frontendRoot, "src", "styles.css"), "utf8");
const js = readFileSync(join(frontendRoot, "src", "app.js"), "utf8");

const requiredHtmlFragments = [
  'class="topbar"',
  'class="library-sidebar"',
  'id="book-list"',
  'class="workspace-main"',
  'class="book-hero"',
  'id="book-cover"',
  'id="overall-progress-ring"',
  'class="actions-rail"',
  'id="translation-provider-profile"',
  'id="chapters-list"',
  'id="message-log"',
  'id="upload-form"',
  'id="lookup-form"',
  'id="translation-form"',
  'id="download-zh"',
  'id="download-bilingual"',
  'id="download-consistency"',
];

for (const fragment of requiredHtmlFragments) {
  assert.ok(html.includes(fragment), `Expected index.html to include ${fragment}`);
}

const requiredCssFragments = [
  ".app-frame",
  ".topbar",
  ".library-sidebar",
  ".workspace-main",
  ".actions-rail",
  ".progress-ring",
  ".chapter-table",
  "@media (max-width: 1180px)",
  "@media (max-width: 760px)",
];

for (const fragment of requiredCssFragments) {
  assert.ok(css.includes(fragment), `Expected styles.css to include ${fragment}`);
}

assert.ok(
  !css.includes("max-width: 1536px"),
  "Expected app shell to use the full viewport instead of a centered max width"
);
assert.ok(
  !css.includes("margin: 0 auto"),
  "Expected app shell not to center the whole workspace with side gutters"
);

const requiredFluidLayoutFragments = [
  "grid-template-columns: minmax(280px, 320px) minmax(0, 1fr) minmax(300px, 340px)",
  "grid-template-rows: auto auto auto minmax(0, 1fr)",
  "grid-template-columns: repeat(2, minmax(0, 1fr))",
  "-webkit-line-clamp: 2",
  ".log-panel",
  "max-height: none",
];

for (const fragment of requiredFluidLayoutFragments) {
  assert.ok(css.includes(fragment), `Expected fluid layout CSS to include ${fragment}`);
}

const appShellBlock = css.match(/\.app-shell\s*\{[^}]+\}/)?.[0] ?? "";
assert.ok(
  appShellBlock.includes("\n  height: 100vh;"),
  "Expected .app-shell to use height: 100vh so side panels fit the viewport"
);

const requiredJsFragments = [
  "overallProgressRing",
  "totalSegments",
  "translatedSegments",
  "failedSegments",
  "remainingSegments",
  'style.setProperty("--progress"',
  "<table>",
  "row-progress",
];

for (const fragment of requiredJsFragments) {
  assert.ok(js.includes(fragment), `Expected app.js to include ${fragment}`);
}
