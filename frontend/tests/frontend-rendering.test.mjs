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
  "appShellClassName",
  "app-shell-reader",
  "readerControlsCollapsed",
  "书架",
  "设置",
  "reader-layout-collapsed",
  "reader-control-rail",
  "PanelLeftOpen",
  "PanelLeftClose",
  "展开阅读控制",
  "收起阅读控制",
  "aria-controls={readerControlsPanelId}",
  "aria-pressed={props.selectedSegmentId === segmentId}",
  "reader-page-controls",
  "个人 AI 设置",
  "规则快照",
  "Provider 运行安全摘要",
  "启动前会自动预检",
  "翻译预检未通过，已阻止启动",
  "真实 provider 翻译",
  "翻译完成后再生成中文 EPUB、双语 EPUB 和一致性报告",
  "术语 / 人名",
  "质量审校",
  "分析候选术语",
  "预览风险段",
  "个人资料",
  "API Key",
  "不会改变真实翻译运行配置",
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

assert.match(
  app,
  /const \[readerControlsCollapsed, setReaderControlsCollapsed\] = useState\(true\);/,
  "Expected reader controls to default to the collapsed, reading-focused state"
);
assert.match(
  app,
  /const appShellClassName = `app-shell \$\{route === "read" \? "app-shell-reader" : ""\}`;/,
  "Expected the reader route to keep its reader shell class"
);
assert.ok(!app.includes("readerGlobalNavOpen"), "Expected reader route to avoid duplicate in-reader global navigation state");
assert.ok(!app.includes("readerGlobalNavId"), "Expected reader route to avoid duplicate in-reader global navigation IDs");
assert.ok(!app.includes("reader-route-chrome"), "Expected reader route to rely on the ordinary left navigation instead of reader chrome");
assert.ok(!app.includes("reader-global-nav"), "Expected reader route to avoid a duplicate global navigation menu");
assert.ok(!app.includes("打开全局导航"), "Expected reader route not to expose duplicate global navigation copy");
assert.ok(!app.includes("<Menu"), "Expected reader route not to use a duplicate navigation menu icon");
assert.match(
  app,
  /className=\{layoutClassName\} data-controls-collapsed=\{readerControlsCollapsed\}/,
  "Expected reader layout to expose collapsed state for CSS"
);
assert.match(
  app,
  /aria-expanded=\{false\}[\s\S]*aria-label="展开阅读控制"/,
  "Expected collapsed rail toggle to expose aria-expanded=false and a Chinese label"
);
assert.match(
  app,
  /<aside id=\{readerControlsPanelId\}[\s\S]*hidden=\{readerControlsCollapsed\}/,
  "Expected full reader controls panel to be hidden while collapsed"
);
assert.match(
  app,
  /aria-expanded=\{!readerControlsCollapsed\}[\s\S]*aria-label="收起阅读控制"/,
  "Expected expanded panel toggle to expose aria-expanded state and a Chinese label"
);
