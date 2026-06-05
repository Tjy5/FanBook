import { escapeHtml } from "../utils/html.js";
import { clampPercentage, formatBytes, formatDateTime, formatDuration, formatNumber } from "../utils/format.js";
import { statusBadgeClass, translateStatus } from "../utils/status.js";
import {
  displayBookTitle,
  normalizedTranslatedTitle,
  renderTranslatedTitle,
  sourceLanguageLabel,
  translateArtifactKind,
} from "../utils/book.js";

export function renderTranslate({ elements, state, providerActions }) {
  const detail = state.currentBookDetail;
  const book = detail?.book;
  const job = detail?.current_job;
  const artifacts = detail?.artifacts ?? [];

  const exportsPanelEl = typeof document !== "undefined" ? document.querySelector(".exports-panel") : null;
  const logPanelEl = typeof document !== "undefined" ? document.querySelector(".log-workspace-panel") : null;

  if (!book) {
    if (exportsPanelEl) exportsPanelEl.style.display = "none";
    if (logPanelEl) logPanelEl.style.display = "none";
    renderProviderProfileSummary({ elements, state, providerActions });
    renderTranslateControls({ elements, state, book, job, artifacts });
    renderTranslateEmptyState({ elements, state });
    return;
  }

  if (exportsPanelEl) exportsPanelEl.style.display = "";
  if (logPanelEl) logPanelEl.style.display = "";

  renderBookMetadata({ elements, book, job });
  renderJob({ elements, job, chapters: detail?.chapters ?? [] });
  renderExports({ elements, artifacts });
  renderChapters({ elements, chapters: detail?.chapters ?? [], job });
  renderProviderProfileSummary({ elements, state, providerActions });
  renderTranslateControls({ elements, state, book, job, artifacts });
  renderLog({ elements, activity: state.activity });
}

export function renderTranslateEmptyState({ elements, state }) {
  const recentBooks = [...(state.books || [])]
    .sort((a, b) => new Date(b.updated_at || b.created_at || 0) - new Date(a.updated_at || a.created_at || 0))
    .slice(0, 3);

  let recentBooksHtml = "";
  if (recentBooks.length > 0) {
    recentBooksHtml = `
      <div class="recent-uploads-box" style="margin-top: 1.5rem; text-align: left; width: 100%; max-width: 450px;">
        <h3 style="font-size: 13px; color: var(--text-primary); margin-bottom: 0.75rem; font-weight: 700; border-bottom: 1px solid var(--line); padding-bottom: 4px;">最近处理的书籍</h3>
        <div style="display: grid; gap: 8px;">
          ${recentBooks.map(b => {
            const title = displayBookTitle(b) || "未命名书籍";
            const progress = b.status === "completed" ? "100%" : (b.progress ? `${Math.round(b.progress * 100)}%` : "进行中");
            return `
              <div style="display: flex; align-items: center; justify-content: space-between; padding: 8px 12px; background: var(--surface); border: 1px solid var(--line); border-radius: 6px;">
                <div style="display: flex; align-items: center; gap: 10px; min-width: 0; flex: 1;">
                  <span style="font-weight: 700; font-size:12px; color: var(--accent); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 260px;">${escapeHtml(title)}</span>
                  <span style="font-size: 10px; color: var(--muted); flex-shrink: 0;">(${escapeHtml(progress)})</span>
                </div>
                <button class="button button-secondary compact" type="button" data-load-recent-book-id="${escapeHtml(b.id)}" style="min-height: 24px; padding: 0 8px; font-size: 11px; flex-shrink: 0;">
                  ${b.status === "completed" ? "阅读" : "管理"}
                </button>
              </div>
            `;
          }).join("")}
        </div>
      </div>
    `;
  }

  if (elements.translateEmptyState) {
    elements.translateEmptyState.innerHTML = `
      <div class="empty-dashboard-sim" style="display: flex; flex-direction: column; align-items: center; justify-content: center; min-height: 400px; padding: 20px; text-align: center; color: var(--muted);">
        <h2 style="font-size: 20px; color: var(--text); margin-bottom: 12px;">开始翻译你的第一本书</h2>
        <p style="width: 28em; margin: 0 auto 20px; max-width: 100%; line-height: 1.6;">
          可以从左侧上传新的 EPUB 书籍并开始翻译。如需继续之前的工作，可在下方快捷加载最近书籍或返回首页选择。
        </p>

        <div style="background: var(--surface-soft); border: 1px solid var(--line); border-radius: 8px; padding: 16px; width: 100%; max-width: 450px; text-align: left; margin-bottom: 15px;">
          <h3 style="font-size: 12px; text-transform: uppercase; color: var(--muted); margin-bottom: 10px; font-weight: 700;">3 步快速指南</h3>
          <ol style="margin-left: 1.25rem; font-size: 12px; display: grid; gap: 6px; color: var(--text-primary);">
            <li>在左侧面板<strong>上传并解析</strong> EPUB 电子书文件。</li>
            <li>选择合适的<strong>翻译配置档</strong>（AI Provider与模型）。</li>
            <li>点击左侧“<strong>开始翻译</strong>”按钮，后台异步队列即可启动。</li>
          </ol>
        </div>

        ${recentBooksHtml}
      </div>
    `;
  }
}

export function renderBookMetadata({ elements, book, job, options = {} }) {
  if (!book) {
    elements.bookMetadata.innerHTML = `
      <div>
        <dt>状态</dt>
        <dd id="book-title-heading">请先载入或上传一本书。</dd>
      </div>
    `;
    return;
  }

  const createdAt = formatDateTime(book.created_at);
  const translatedTitle = options.isPreview
    ? book.translated_title
    : renderTranslatedTitle(book);
  const sourceLanguage = sourceLanguageLabel(book.source_language);

  elements.bookMetadata.innerHTML = `
    <div>
      <dt>原标题</dt>
      <dd id="book-title-heading">${escapeHtml(book.title)}</dd>
    </div>
    <div>
      <dt>译后标题</dt>
      <dd>${escapeHtml(translatedTitle || "待生成")} <button class="text-button inline-action" type="button" data-edit-translated-title>编辑</button></dd>
    </div>
    <div>
      <dt>书籍 ID</dt>
      <dd>${escapeHtml(book.id)}</dd>
    </div>
    <div>
      <dt>文件名</dt>
      <dd>${escapeHtml(book.filename)}</dd>
    </div>
    <div>
      <dt>源语言</dt>
      <dd>${escapeHtml(sourceLanguage)}</dd>
    </div>
    <div>
      <dt>创建时间</dt>
      <dd>${escapeHtml(createdAt)}</dd>
    </div>
  `;
}

export function renderJob({ elements, job, chapters }) {
  const totals = chapters.reduce(
    (accumulator, chapter) => {
      accumulator.total += Number(chapter.total_segments) || 0;
      accumulator.translated += Number(chapter.translated_segments) || 0;
      accumulator.failed += Number(chapter.failed_segments) || 0;
      return accumulator;
    },
    { total: 0, translated: 0, failed: 0 }
  );
  const summaryTotals = totalsFromJob(job, totals);
  const percentage = clampPercentage((job?.progress ?? progressFromChapters(summaryTotals)) * 100);
  const badge = statusBadgeClass(job?.status);
  const remaining = Math.max(0, summaryTotals.total - summaryTotals.translated - summaryTotals.failed);

  elements.jobStatusPill.className = `status-pill ${badge}`;
  elements.jobStatusPill.textContent = translateStatus(job?.status ?? "idle");
  elements.jobProgressNumber.textContent = `${Math.round(percentage)}%`;
  elements.jobProgressBar.style.width = `${percentage}%`;
  elements.overallProgressRing.style.setProperty("--progress", `${percentage}%`);
  elements.overallProgressRing.setAttribute("aria-label", `整体进度 ${Math.round(percentage)}%`);
  elements.totalSegments.textContent = formatNumber(summaryTotals.total);
  elements.translatedSegments.textContent = formatNumber(summaryTotals.translated);
  elements.failedSegments.textContent = formatNumber(summaryTotals.failed);
  elements.remainingSegments.textContent = formatNumber(remaining);
  elements.jobProgressLabel.textContent = job
    ? `预计剩余时间：${estimateRemainingTime(job, summaryTotals, percentage)}`
    : "当前没有活动任务";
}

export function renderExports({ elements, artifacts }) {
  const byKind = new Map(artifacts.map((artifact) => [artifact.kind, artifact]));
  const cards = [
    renderExportCard("zh", "中文 EPUB", byKind.get("zh")),
    renderExportCard("bilingual", "中英双语 EPUB", byKind.get("bilingual")),
    renderExportCard("consistency_report", "一致性报告", byKind.get("consistency_report")),
  ];
  elements.exportList.innerHTML = cards.join("");
}

export function renderExportCard(kind, label, artifact) {
  const status = translateStatus(artifact?.status ?? "pending");
  const sizeText = artifact?.size ? formatBytes(artifact.size) : "等待生成";

  return `
    <article>
      <strong>${escapeHtml(label)}</strong>
      <span>${escapeHtml(status)} · ${escapeHtml(sizeText)}</span>
    </article>
  `;
}

export function renderTranslateControls({ elements, state, book, job, artifacts }) {
  const hasBook = Boolean(book);
  const jobStatus = String(job?.status || "").toLowerCase();
  const isActiveJob = ["pending", "running"].includes(jobStatus);
  const canResume = hasBook && ["failed", "canceled"].includes(jobStatus);
  const hasProviderProfile = Boolean(state.providerProfiles?.length && state.selectedProviderProfileName);

  setButtonDisabled(elements.translateButton, !hasBook || !hasProviderProfile || isActiveJob);
  setButtonDisabled(elements.resumeButton, !canResume);
  setButtonDisabled(elements.stopPollingButton, !hasBook || !isActiveJob);
  setButtonDisabled(elements.downloadZhButton, !canDownloadArtifact("zh", { book, job, artifacts }));
  setButtonDisabled(elements.downloadBilingualButton, !canDownloadArtifact("bilingual", { book, job, artifacts }));
  setButtonDisabled(
    elements.downloadConsistencyButton,
    !canDownloadArtifact("consistency_report", { book, job, artifacts })
  );
}

function setButtonDisabled(button, isDisabled) {
  if (button) {
    button.disabled = isDisabled;
  }
}

function canDownloadArtifact(kind, { book, job, artifacts }) {
  if (!book) {
    return false;
  }
  if (artifacts.some((artifact) => artifact.kind === kind && isReadyArtifact(artifact))) {
    return true;
  }
  return isExportableBook(book, job);
}

function isReadyArtifact(artifact) {
  return String(artifact?.status || "").toLowerCase() === "ready";
}

function isExportableBook(book, job) {
  const bookStatus = String(book?.status || "").toLowerCase();
  const jobStatus = String(job?.status || "").toLowerCase();
  return bookStatus === "completed" || jobStatus === "completed";
}

export function renderChapters({ elements, chapters, job }) {
  if (!chapters.length) {
    elements.chaptersList.innerHTML =
      '<div class="empty-state">载入书籍后，这里会显示章节进度。</div>';
    return;
  }

  const totals = chapters.reduce(
    (accumulator, chapter) => {
      accumulator.total += Number(chapter.total_segments) || 0;
      accumulator.translated += Number(chapter.translated_segments) || 0;
      accumulator.failed += Number(chapter.failed_segments) || 0;
      return accumulator;
    },
    { total: 0, translated: 0, failed: 0 }
  );
  const summaryTotals = totalsFromJob(job, totals);
  const overallProgress = summaryTotals.total > 0
    ? (summaryTotals.translated / summaryTotals.total) * 100
    : 0;
  const rows = chapters
    .map((chapter) => {
      const total = Number(chapter.total_segments) || 0;
      const translated = Number(chapter.translated_segments) || 0;
      const failed = Number(chapter.failed_segments) || 0;
      const progress = total > 0 ? (translated / total) * 100 : 0;

      return `
        <tr>
          <td>${escapeHtml(chapter.order)}. ${escapeHtml(chapter.title)}</td>
          <td>${formatNumber(total)}</td>
          <td>${formatNumber(translated)}</td>
          <td>${formatNumber(failed)}</td>
          <td>
            <span class="row-progress"><i style="width:${clampPercentage(progress)}%"></i></span>
            <strong>${Math.round(progress)}%</strong>
          </td>
        </tr>
      `;
    })
    .join("");

  elements.chaptersList.innerHTML = `
    <table>
      <thead>
        <tr>
          <th>章节</th>
          <th>段落数</th>
          <th>已翻译</th>
          <th>失败</th>
          <th>进度</th>
        </tr>
      </thead>
      <tbody>${rows}</tbody>
      <tfoot>
        <tr>
          <td>总计</td>
          <td>${formatNumber(summaryTotals.total)}</td>
          <td>${formatNumber(summaryTotals.translated)}</td>
          <td>${formatNumber(summaryTotals.failed)}</td>
          <td>
            <span class="row-progress"><i style="width:${clampPercentage(overallProgress)}%"></i></span>
            <strong>${Math.round(overallProgress)}%</strong>
          </td>
        </tr>
      </tfoot>
    </table>
  `;
}

export function renderProviderProfileSummary({ elements, state, providerActions }) {
  const select = elements.translationProviderProfileSelect;
  const summary = elements.translationProviderSummary;
  const profiles = state.providerProfiles;

  if (!profiles.length) {
    select.disabled = true;
    select.innerHTML = '<option value="">未找到可用配置</option>';
    summary.textContent = "当前没有可用的翻译配置档。";
    elements.providerStatusLabel.textContent = "不可用";
    return;
  }

  providerActions.ensureSelectedProviderProfile();
  select.disabled = false;
  select.innerHTML = profiles
    .map((profile) => {
      const profileName = providerActions.profileIdentifier(profile);
      const suffix = profile.is_default ? "（默认）" : "";
      return `<option value="${escapeHtml(profileName)}">${escapeHtml(profileName)}${suffix}</option>`;
    })
    .join("");
  select.value = state.selectedProviderProfileName || "";

  const selectedProfile = providerActions.getSelectedProviderProfile();
  if (!selectedProfile) {
    summary.textContent = "请选择一个翻译配置档。";
    elements.providerStatusLabel.textContent = "未选择";
    return;
  }

  const providerName = selectedProfile.provider_name || "-";
  const modelName = selectedProfile.default_model_name || "-";
  const configuredText = selectedProfile.configured ? "已配置" : "未配置";
  const rpmLimit = selectedProfile.max_requests_per_minute ?? "-";
  const globalConcurrency = selectedProfile.global_max_concurrency ?? "-";
  const perChapterConcurrency = selectedProfile.per_chapter_concurrency ?? "-";
  elements.providerStatusLabel.textContent = `${providerName} (${modelName})`;
  summary.textContent =
    `当前将使用配置档 ${providerActions.profileIdentifier(selectedProfile)}，provider 为 ${providerName}，模型为 ${modelName}，RPM 上限 ${rpmLimit}，全局并发 ${globalConcurrency}，单章并发 ${perChapterConcurrency}，状态 ${configuredText}。`;
}

export function renderLog({ elements, activity }) {
  if (!activity.length) {
    elements.messageLog.innerHTML =
      '<div class="empty-state">暂无活动记录。你的操作和服务端返回会显示在这里。</div>';
    return;
  }

  elements.messageLog.innerHTML = activity
    .slice(0, 10)
    .map(
      (entry) => `
        <article class="log-entry">
          <span class="log-time">${escapeHtml(entry.time)}</span>
          <p class="log-message">${escapeHtml(entry.message)}</p>
        </article>
      `
    )
    .join("");
}

export function progressFromChapters(totals) {
  if (!totals.total) {
    return 0;
  }
  return totals.translated / totals.total;
}

export function totalsFromJob(job, fallbackTotals) {
  const total = Number(job?.total_segments);
  const translated = Number(job?.translated_segments);
  const failed = Number(job?.failed_segments);
  return {
    total: Number.isFinite(total) && total > 0 ? total : fallbackTotals.total,
    translated: Number.isFinite(translated) && translated >= 0
      ? translated
      : fallbackTotals.translated,
    failed: Number.isFinite(failed) && failed >= 0 ? failed : fallbackTotals.failed,
  };
}

export function estimateRemainingTime(job, totals, percentage) {
  const explicitSeconds = Number(job?.estimated_remaining_seconds);
  if (Number.isFinite(explicitSeconds) && explicitSeconds > 0) {
    return formatDuration(explicitSeconds);
  }
  if (!totals.total || percentage <= 0 || percentage >= 100) {
    return percentage >= 100 ? "0 分钟" : "计算中";
  }

  const remaining = Math.max(0, totals.total - totals.translated - totals.failed);
  if (!remaining) {
    return "0 分钟";
  }

  return formatDuration(Math.round(remaining * 2.2));
}
