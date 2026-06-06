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
  'localStorage.getItem(PROVIDER_PROFILE_STORAGE_KEY)',
  'window.location.hash = `#/${nextRoute}`',
  'return "home"',
]) {
  assert.ok(app.includes(fragment), `Expected app contract fragment ${fragment}`);
}

for (const fragment of [
  "export class ApiClient",
  "authCsrf",
  "authLogin",
  "listBooks",
  "readerSegments",
  "notesExport",
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
]) {
  assert.ok(types.includes(fragment), `Expected type contract fragment ${fragment}`);
}
