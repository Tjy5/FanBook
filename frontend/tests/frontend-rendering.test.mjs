import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, "..");
const app = readFileSync(join(frontendRoot, "src", "main.tsx"), "utf8");

for (const fragment of [
  "<HomePage",
  "<TranslatePage",
  "<ReaderPage",
  "<AdminPage",
  "开始翻译你的第一本书",
  "Private team workspace",
  "首次管理员通过部署环境变量初始化",
  "disabled={!props.isMemberLike",
  "disabled={!ready}",
  "statusBadgeClass(props.job?.status || \"idle\")",
  "props.isMemberLike && segmentId",
  "props.onUpdateRoles(user.id",
]) {
  assert.ok(app.includes(fragment), `Expected React rendering source to include ${fragment}`);
}
