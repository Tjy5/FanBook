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
  "csrf",
  "generateArtifact",
  "downloadArtifact",
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
  ".reader-layout",
  ".settings-layout",
  ".admin-grid",
  ".auth-shell",
  "@media (max-width: 1040px)",
  "@media (max-width: 760px)",
]) {
  assert.ok(css.includes(fragment), `Expected CSS to include ${fragment}`);
}

assert.ok(
  css.includes("width: 24em;") && css.includes("max-width: 100%;"),
  "Expected empty-state body text to stay within mobile viewports"
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
