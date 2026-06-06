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
  "<SettingsPage",
  "<AdminPage",
  "开始翻译你的第一本书",
  "AI book translation reader",
  "我的书架",
  "Fanbook 演示书",
  "打开演示书",
  "先读演示书，再上传自己的 EPUB",
  "DEMO_BOOK_ID",
  "READER_SEGMENTS_PER_PAGE",
  "reader-page-controls",
  "个人 AI 设置",
  "个人资料",
  "API Key",
  "保存设置",
  "SETTINGS_DRAFT_STORAGE_KEY",
  "管理员导航",
  "disabled={!props.isMemberLike",
  "disabled={props.isDemoBook}",
  "disabled={!ready}",
  "statusBadgeClass(props.job?.status || \"idle\")",
  "props.isMemberLike && segmentId",
  "props.onUpdateRoles(user.id",
]) {
  assert.ok(app.includes(fragment), `Expected React rendering source to include ${fragment}`);
}
