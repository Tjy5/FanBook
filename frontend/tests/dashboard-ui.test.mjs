import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import assert from "node:assert/strict";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, "..");
const readFrontendFile = (...segments) => readFileSync(join(frontendRoot, ...segments), "utf8");

const html = readFrontendFile("index.html");
const css = readFrontendFile("src", "styles.css");
const app = readFrontendFile("src", "main.tsx");
const apiClient = readFrontendFile("src", "api", "client.ts");
const packageJson = JSON.parse(readFrontendFile("package.json"));

for (const path of [
  ["package.json"],
  ["vite.config.ts"],
  ["tsconfig.json"],
  ["src", "main.tsx"],
  ["src", "types.ts"],
  ["src", "api", "client.ts"],
  ["src", "styles.css"],
]) {
  assert.ok(existsSync(join(frontendRoot, ...path)), `Expected ${path.join("/")} to exist`);
}

assert.equal(packageJson.type, "module");
assert.equal(packageJson.scripts.dev, "vite --host 0.0.0.0");
assert.equal(packageJson.scripts.typecheck, "tsc --noEmit");
assert.match(packageJson.scripts.build, /tsc --noEmit/);
assert.ok(packageJson.dependencies.react, "Expected React dependency");
assert.ok(packageJson.devDependencies.vite, "Expected Vite dev dependency");
assert.ok(packageJson.devDependencies.typescript, "Expected TypeScript dev dependency");

assert.ok(html.includes('id="root"'), "Expected Vite root element");
assert.ok(html.includes('/src/main.tsx'), "Expected Vite React TypeScript entry");
assert.ok(!html.includes("./src/app.js"), "Expected old native module entry to be removed");

for (const fragment of [
  "createRoot",
  "StrictMode",
  "ApiClient",
  "authChecked",
  "login",
  "logout",
  "currentUser.roles",
  "hasAnyRole",
  "LOGIN_VIEW_COPY",
  "auth-panel-${loginMode}",
  "管理员入口",
  "测试账号 2 / 2",
  "csrf",
  "generateArtifact",
  "downloadArtifact",
  "translationPreflight",
  "ProviderSafetyStrip",
  "PreflightPanel",
  "ReaderPage",
  "SettingsPage",
  "AdminPage",
  "BookRow",
  "DEMO_BOOK_LIST_ITEM",
  '"admin-users"',
  '"settings"',
  "loadReaderSegments",
  "refreshBookForPolling",
  "POLL_INTERVAL_MS",
]) {
  assert.ok(app.includes(fragment), `Expected React app to include ${fragment}`);
}

for (const fragment of [
  "/auth/csrf",
  "/auth/login",
  "/auth/logout",
  "/auth/me",
  "credentials: \"same-origin\"",
  "csrfState.headerName",
  "csrfState.token",
  "createEndpoint",
  "/exports/zh",
  "/reports/consistency",
  "/translation-glossary-analysis",
  "/translation-glossary-candidates/accept",
  "/translation-jobs/preflight",
]) {
  assert.ok(apiClient.includes(fragment), `Expected API client to include ${fragment}`);
}

for (const fragment of [
  "/* ========== TOKENS ========== */",
  "/* ========== LAYOUT ========== */",
  "/* ========== PAGE: HOME ========== */",
  "/* ========== PAGE: TRANSLATE ========== */",
  "/* ========== PAGE: READER ========== */",
  "/* ========== PAGE: SETTINGS ========== */",
  "/* ========== PAGE: ADMIN ========== */",
  "/* ========== AUTH ========== */",
  ".app-shell",
  ".translate-grid",
  ".provider-safety-strip",
  ".preflight-panel",
  ".reader-layout",
  ".settings-layout",
  ".admin-grid",
  ".auth-shell",
  ".auth-shell-admin",
  ".auth-panel-admin",
  ".auth-mode-banner",
  "@media (max-width: 1040px)",
  "@media (max-width: 760px)",
]) {
  assert.ok(css.includes(fragment), `Expected CSS to include ${fragment}`);
}

assert.ok(
  css.includes("width: 24em;") && css.includes("max-width: 100%;"),
  "Expected empty-state body text to stay within mobile viewports"
);

assert.ok(css.includes(".app-shell-reader"), "Expected reader route to keep a reader-specific shell class");
const readerSidebarRules = css.match(/\.app-shell-reader[^{]*\.app-sidebar[^{]*{[^}]*}/g) || [];
for (const rule of readerSidebarRules) {
  assert.doesNotMatch(
    rule,
    /\b(display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0|width\s*:\s*0|max-width\s*:\s*0|transform\s*:\s*translateX\(\s*-[^)]+\))/i,
    "Expected reader route sidebar rules not to hide, collapse, or move the ordinary persistent global sidebar"
  );
}
assert.doesNotMatch(
  css,
  /\.app-shell-reader\s*{[^}]*grid-template-columns:/,
  "Expected reader shell not to collapse the app layout into a single column"
);
assert.match(
  css,
  /\.app-shell-reader \.page-view\.active\.reader-view\s*{[\s\S]*grid-template-rows: minmax\(0, 1fr\);/,
  "Expected reader view to reserve most viewport height for the reading canvas"
);
assert.ok(!css.includes(".reader-route-chrome"), "Expected reader route not to duplicate global route navigation chrome");
assert.ok(!css.includes(".reader-global-nav"), "Expected reader route not to keep a duplicate global navigation menu");
assert.match(
  css,
  /\.reader-book-stage,\s*\.reader-segments\s*{[\s\S]*width: 100%;/,
  "Expected bilingual reader stage to use the full available reading column"
);
assert.ok(css.includes("width: min(100%, 980px);"), "Expected single-language reader stage to keep a wider but readable cap");
assert.ok(!css.includes("width: min(100%, 1040px);"), "Expected reader stage to stop using the old bilingual width cap");
assert.ok(!css.includes("width: min(100%, 760px);"), "Expected reader stage to stop using the old single-language width cap");
assert.match(
  css,
  /\.reader-layout\s*{[\s\S]*grid-template-columns: minmax\(52px, 64px\) minmax\(0, 1fr\) clamp\(208px, 18vw, 284px\);/,
  "Expected collapsed reader layout to reserve a compact control rail and a side notes column"
);
assert.match(
  css,
  /\.reader-layout\s*{[\s\S]*grid-template-areas: "controls reader notes";/,
  "Expected reader notes to sit beside the first-screen reading stage on desktop"
);
assert.match(
  css,
  /\.reader-layout\s*{[\s\S]*grid-template-rows: minmax\(0, 1fr\);/,
  "Expected desktop reader layout to fit the reading workspace into one viewport row"
);
assert.match(
  css,
  /\.reader-layout-expanded\s*{[\s\S]*grid-template-columns: minmax\(190px, 226px\) minmax\(0, 1fr\) clamp\(200px, 16vw, 270px\);/,
  "Expected expanded reader layout to restore controls while preserving the side notes column"
);
assert.match(
  css,
  /\.reader-book-stage,\s*\.reader-segments\s*{[\s\S]*--reader-page-min-height: 0;/,
  "Expected desktop reader pages to avoid forcing the whole reader route to scroll"
);
assert.match(
  css,
  /\.reader-book-stage,\s*\.reader-segments\s*{[\s\S]*height: 100%;/,
  "Expected desktop reader stage to fill the available reader row instead of extending below it"
);
assert.match(
  css,
  /\.reader-page-content\s*{[\s\S]*max-width: 74ch;/,
  "Expected wide reader pages to keep text measure readable inside larger pages"
);
assert.match(
  css,
  /\.reader-page-content\s*{[\s\S]*overflow: auto;/,
  "Expected overlong reader text to scroll inside the page instead of pushing notes below the viewport"
);
assert.match(
  css,
  /\.reader-marginalia,\s*\.segment-notes-panel\s*{[\s\S]*grid-template-rows: auto minmax\(0, 1fr\);/,
  "Expected the notes panel to behave as a compact side companion with its own scroll area"
);
assert.match(
  css,
  /@media \(max-width: 1040px\)[\s\S]*\.reader-layout\s*{[\s\S]*grid-template-areas:\s*"controls"\s*"reader"\s*"notes";/,
  "Expected tablet reader layout to stack controls, reader, and notes"
);
assert.match(
  css,
  /@media \(max-width: 1040px\)[\s\S]*\.reader-layout-collapsed,\s*\.reader-layout-expanded\s*{[\s\S]*grid-template-columns: 1fr;/,
  "Expected collapsed and expanded reader layouts to use one column on tablet"
);
assert.match(
  css,
  /@media \(max-width: 760px\)[\s\S]*\.reader-book-spread\s*{[\s\S]*grid-template-columns: minmax\(0, 1fr\);/,
  "Expected mobile bilingual reader pages to stack vertically"
);

for (const fragment of [
  "DEMO_DETAIL",
  "Book Three: The Prophet",
  "/books/${bookId}/translate`",
  "/books/${bookId}/resume`",
  "/books/${bookId}/export/zh`",
  "content_base64",
  "response.book_id",
]) {
  assert.ok(!app.includes(fragment), `Expected React app not to include deprecated fragment ${fragment}`);
}
