import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, "..");
const packageJson = JSON.parse(readFileSync(join(frontendRoot, "package.json"), "utf8"));
const app = readFileSync(join(frontendRoot, "src", "main.tsx"), "utf8");
const apiClient = readFileSync(join(frontendRoot, "src", "api", "client.ts"), "utf8");
const types = readFileSync(join(frontendRoot, "src", "types.ts"), "utf8");

assert.ok(packageJson.scripts.test.includes("node --test"));
assert.ok(packageJson.scripts.typecheck.includes("tsc --noEmit"));
assert.ok(packageJson.scripts.build.includes("vite build"));

for (const fragment of [
  'const STORAGE_KEY = "fanbook.currentBookId"',
  "const POLL_INTERVAL_MS = 3000",
  "const DEMO_BOOK_STORAGE_VALUE = \"demo\"",
  "type LoadBookOptions = { silent?: boolean; syncUrl?: boolean }",
  'type LoginMode = "user" | "admin"',
  "const LOGIN_VIEW_COPY",
  'const loginMode: LoginMode = route === "admin-users" ? "admin" : "user"',
  "cloneDemoBookDetail",
  "bookIdFromInput",
  'localStorage.getItem(PROVIDER_PROFILE_STORAGE_KEY)',
  'window.location.hash = `#/${routeToHash(nextRoute)}`',
  'return "library"',
  'return "admin-users"',
]) {
  assert.ok(app.includes(fragment), `Expected app contract fragment ${fragment}`);
}

assert.ok(
  app.includes('const requestedBookId = new URL(window.location.href).searchParams.get("bookId");') &&
    app.includes("if (requestedBookId)") &&
    app.includes("void loadBook(bookIdFromStorage(requestedBookId), { silent: true });"),
  "Expected explicit bookId query parameter restore to remain supported"
);

assert.ok(
  app.includes("void loadBook(bookIdFromStorage(remembered), { silent: true, syncUrl: false });"),
  "Expected remembered localStorage book restore not to write bookId into clean URLs"
);

assert.ok(
  app.includes("if (options.syncUrl ?? true)") &&
    app.includes("updateBookIdSearch(detail.book.id);") &&
    app.includes("updateBookIdSearch(DEMO_BOOK_ID);"),
  "Expected explicit book loads, including demo, to keep writing shareable bookId URLs"
);

assert.ok(
  app.includes('if (loginMode === "admin" && !hasRole(user, "ADMIN"))') &&
    app.includes('window.location.hash = "#/library";') &&
    app.includes("不是管理员，已切回我的书架。"),
  "Expected MEMBER users logging in through admin mode to be redirected to the library"
);

assert.ok(
  app.includes('window.location.hash = "#/admin-users";') &&
    app.includes("已登录为管理员") &&
    app.includes("auth-panel-${loginMode}"),
  "Expected ADMIN login mode to route to admin user management with distinct UI fragments"
);

for (const fragment of [
  "export class ApiClient",
  "authCsrf",
  "authLogin",
  "listBooks",
  "readerSegments",
  "notesExport",
  "glossaryAnalysis",
  "acceptGlossaryCandidates",
  "extractFilename",
  "normalizeError",
]) {
  assert.ok(apiClient.includes(fragment), `Expected API contract fragment ${fragment}`);
}

for (const fragment of [
  'export type Role = "ADMIN" | "MEMBER" | "VIEWER"',
  "export interface CurrentUser",
  "export interface BookDetail",
  "export interface ReaderSegment",
  "export interface SegmentNote",
  "export interface TranslationPromptProfile",
  "export interface GlossaryAnalysisResult",
  "export interface GlossaryImportResult",
]) {
  assert.ok(types.includes(fragment), `Expected type contract fragment ${fragment}`);
}
