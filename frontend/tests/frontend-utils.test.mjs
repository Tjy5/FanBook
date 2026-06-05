import assert from "node:assert/strict";

import { escapeHtml } from "../src/utils/html.js";
import { clampPercentage, formatBytes, formatDuration, formatNumber } from "../src/utils/format.js";
import { bookStatusClass, statusBadgeClass, translateStatus } from "../src/utils/status.js";
import {
  bookCoverInitials,
  displayBookTitle,
  renderTranslatedTitle,
  sourceLanguageLabel,
  translateArtifactKind,
} from "../src/utils/book.js";

assert.equal(
  escapeHtml('<b title="x">Tom & Jerry</b>'),
  "&lt;b title=&quot;x&quot;&gt;Tom &amp; Jerry&lt;/b&gt;"
);
assert.equal(formatNumber(12345), "12,345");
assert.equal(formatDuration(60), "1 分钟");
assert.equal(formatDuration(3600), "1 小时");
assert.equal(formatDuration(3660), "1 小时 1 分钟");
assert.equal(formatBytes(0), "0 B");
assert.equal(formatBytes(1536), "1.5 KB");
assert.equal(clampPercentage(-10), 0);
assert.equal(clampPercentage(120), 100);
assert.equal(statusBadgeClass("completed"), "status-success");
assert.equal(statusBadgeClass("running"), "status-running");
assert.equal(statusBadgeClass("failed"), "status-failed");
assert.equal(translateStatus("queued"), "待翻译");
assert.equal(bookStatusClass("completed"), "done");
assert.equal(sourceLanguageLabel("en"), "英文 (en)");
assert.equal(sourceLanguageLabel("zh"), "中文 (zh)");
assert.equal(translateArtifactKind("bilingual"), "中英双语 EPUB");
assert.equal(
  displayBookTitle({ title: "Original", translated_title: "译名", title_translation_status: "completed" }),
  "译名"
);
assert.equal(renderTranslatedTitle({ translated_title: "", title_translation_status: "failed" }), "未生成");
assert.equal(bookCoverInitials({ title: "Fanbook" }), "FA");
