import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import assert from "node:assert/strict";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, "..");
const readFrontendFile = (...segments) => readFileSync(join(frontendRoot, ...segments), "utf8");
const html = readFrontendFile("index.html");
const css = readFrontendFile("src", "styles.css");

const moduleFiles = [
  ["src", "app.js"],
  ["src", "state.js"],
  ["src", "api", "index.js"],
  ["src", "router.js"],
  ["src", "dom.js"],
  ["src", "events.js"],
  ["src", "pages", "home.js"],
  ["src", "pages", "translate.js"],
  ["src", "pages", "reader.js"],
  ["src", "components", "shared.js"],
  ["src", "utils", "html.js"],
  ["src", "utils", "format.js"],
  ["src", "utils", "status.js"],
  ["src", "utils", "book.js"],
];
const existingModuleFiles = moduleFiles.filter((segments) => existsSync(join(frontendRoot, ...segments)));
const js = existingModuleFiles.map((segments) => readFrontendFile(...segments)).join("\n");

assert.ok(html.includes('<script type="module"'), "Expected index.html to keep a single ES module entry");

const requiredModulePaths = [
  ["src", "state.js"],
  ["src", "api", "index.js"],
  ["src", "router.js"],
  ["src", "dom.js"],
  ["src", "events.js"],
  ["src", "pages", "home.js"],
  ["src", "pages", "translate.js"],
  ["src", "pages", "reader.js"],
  ["src", "components", "shared.js"],
  ["src", "utils", "html.js"],
  ["src", "utils", "format.js"],
  ["src", "utils", "status.js"],
  ["src", "utils", "book.js"],
];

for (const segments of requiredModulePaths) {
  const path = join(frontendRoot, ...segments);
  assert.ok(existsSync(path), `Expected module file ${segments.join("/")}`);
}

const requiredHtmlFragments = [
  'class="topbar"',
  'class="page-nav"',
  'href="#/home"',
  'href="#/translate"',
  'href="#/read"',
  'data-route-link="home"',
  'data-route-link="translate"',
  'data-route-link="read"',
  'data-page="home"',
  'data-page="translate"',
  'data-page="read"',
  'id="home-book-list"',
  'id="home-running-count"',
  'id="home-selected-book"',
  'id="translate-empty-state"',
  'id="read-empty-state"',
  'id="reader-empty-action"',
  'class="book-hero',
  'id="book-cover"',
  'id="overall-progress-ring"',
  'id="translation-provider-profile"',
  'id="chapters-list"',
  'id="message-log"',
  'id="upload-form"',
  'id="lookup-form"',
  'id="translation-form"',
  'id="download-zh"',
  'id="download-bilingual"',
  'id="download-consistency"',
  'id="reader-panel"',
  'id="reader-mode"',
  'id="reader-chapter-select"',
  'id="reader-segments"',
  'id="segment-notes-panel"',
  'id="notes-export"',
];

for (const fragment of requiredHtmlFragments) {
  assert.ok(html.includes(fragment), `Expected index.html to include ${fragment}`);
}

const requiredCssFragments = [
  ".topbar",
  ".page-nav",
  ".page-view",
  ".page-view.active",
  ".home-grid",
  ".translate-grid",
  ".reader-layout",
  ".progress-ring",
  ".chapter-table",
  "@media (max-width: 1040px)",
  "@media (max-width: 760px)",
];

for (const fragment of requiredCssFragments) {
  assert.ok(css.includes(fragment), `Expected styles.css to include ${fragment}`);
}

assert.ok(
  css.includes("width: 24em;") && css.includes("max-width: 100%;"),
  "Expected empty-state body text to stay within mobile viewports"
);

const requiredCssSections = [
  "/* ========== TOKENS ========== */",
  "/* ========== BASE ========== */",
  "/* ========== LAYOUT ========== */",
  "/* ========== COMPONENTS ========== */",
  "/* ========== PAGE: HOME ========== */",
  "/* ========== PAGE: TRANSLATE ========== */",
  "/* ========== PAGE: READER ========== */",
  "/* ========== RESPONSIVE ========== */",
];

for (const fragment of requiredCssSections) {
  assert.ok(css.includes(fragment), `Expected styles.css to include section ${fragment}`);
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
  "activePage",
  "normalizeRoute",
  "applyRoute",
  "navigateTo",
  "syncRouteHash",
  "renderRoute",
  "window.location.hash",
  "const routeHash = `#/${route}`",
  "url.searchParams.set(\"bookId\"",
  "overallProgressRing",
  "totalSegments",
  "translatedSegments",
  "failedSegments",
  "remainingSegments",
  'style.setProperty("--progress"',
  "<table>",
  "row-progress",
  "loadBooks",
  "renderBookList",
  "updateTranslatedTitle",
  "new FormData()",
  'formData.append("file"',
  "response.bookId",
  "providerName",
  "modelName",
  "/translation-jobs",
  "/translation-jobs/resume",
  "/exports/zh",
  "/exports/bilingual",
  "/translated-title",
  "readerInfo",
  "loadReader",
  "renderReaderSegments",
  "createSegmentNote",
  "/reader/info",
  "/notes/export",
];

for (const fragment of requiredJsFragments) {
  assert.ok(js.includes(fragment), `Expected app.js to include ${fragment}`);
}

const requiredInteractionFragments = [
  'elements.segmentNotesPanel.addEventListener("click"',
  "isInteractiveControl",
  "event.preventDefault()",
  'class="reader-segment-main"',
];

for (const fragment of requiredInteractionFragments) {
  assert.ok(js.includes(fragment), `Expected frontend interactions to include ${fragment}`);
}

assert.ok(
  !js.includes('<article class="reader-segment${layoutClass}${activeClass}" data-reader-segment-id='),
  "Expected reader segment selection target not to wrap the note button"
);

const deprecatedJsFragments = [
  "DEMO_DETAIL",
  "Book Three: The Prophet",
  "/books/${bookId}/translate`",
  "/books/${bookId}/resume`",
  "/books/${bookId}/export/zh`",
  "/books/${bookId}/export/bilingual`",
  "content_base64",
  "response.book_id",
  "response.job_id",
  "profileName:",
];

for (const fragment of deprecatedJsFragments) {
  assert.ok(!js.includes(fragment), `Expected app.js not to include deprecated fragment ${fragment}`);
}

const deprecatedHtmlFragments = [
  'class="actions-rail"',
  'class="workspace-main"',
  'class="workspace-grid"',
];

for (const fragment of deprecatedHtmlFragments) {
  assert.ok(!html.includes(fragment), `Expected index.html not to include deprecated fragment ${fragment}`);
}

const deprecatedCssFragments = [
  ".actions-rail",
  ".workspace-main",
  ".workspace-grid",
  "grid-template-columns: minmax(280px, 320px) minmax(0, 1fr) minmax(300px, 340px)",
];

for (const fragment of deprecatedCssFragments) {
  assert.ok(!css.includes(fragment), `Expected styles.css not to include deprecated fragment ${fragment}`);
}
