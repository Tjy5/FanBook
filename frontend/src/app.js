const API_BASE = window.FANBOOK_API_BASE || "/api";
const STORAGE_KEY = "fanbook.currentBookId";
const PROVIDER_PROFILE_STORAGE_KEY = "fanbook.translationProviderProfile";
const POLL_INTERVAL_MS = 3000;

const state = {
  currentBookId: null,
  currentBookDetail: null,
  pollTimer: null,
  activity: [],
  providerProfiles: [],
  defaultProviderProfileName: null,
  selectedProviderProfileName: window.localStorage.getItem(PROVIDER_PROFILE_STORAGE_KEY),
};

const elements = {
  apiBaseLabel: document.querySelector("#api-base-label"),
  currentBookLabel: document.querySelector("#current-book-label"),
  pollingLabel: document.querySelector("#polling-label"),
  uploadForm: document.querySelector("#upload-form"),
  lookupForm: document.querySelector("#lookup-form"),
  translationForm: document.querySelector("#translation-form"),
  refreshButton: document.querySelector("#refresh-book"),
  useLatestButton: document.querySelector("#use-latest-book"),
  stopPollingButton: document.querySelector("#stop-polling-button"),
  resumeButton: document.querySelector("#resume-button"),
  downloadZhButton: document.querySelector("#download-zh"),
  downloadBilingualButton: document.querySelector("#download-bilingual"),
  downloadConsistencyButton: document.querySelector("#download-consistency"),
  uploadButton: document.querySelector("#upload-button"),
  translateButton: document.querySelector("#translate-button"),
  translationProviderProfileSelect: document.querySelector("#translation-provider-profile"),
  translationProviderSummary: document.querySelector("#translation-provider-summary"),
  bookIdInput: document.querySelector("#book-id-input"),
  bookMetadata: document.querySelector("#book-metadata"),
  exportList: document.querySelector("#export-list"),
  chaptersList: document.querySelector("#chapters-list"),
  messageLog: document.querySelector("#message-log"),
  detailPanel: document.querySelector("#book-detail-panel"),
  jobStatusPill: document.querySelector("#job-status-pill"),
  jobProgressLabel: document.querySelector("#job-progress-label"),
  jobProgressNumber: document.querySelector("#job-progress-number"),
  jobProgressBar: document.querySelector("#job-progress-bar"),
};

const endpoint = {
  createBook: () => `${API_BASE}/books`,
  listProviders: () => `${API_BASE}/providers`,
  getBook: (bookId) => `${API_BASE}/books/${bookId}`,
  startTranslation: (bookId) => `${API_BASE}/books/${bookId}/translate`,
  resumeTranslation: (bookId) => `${API_BASE}/books/${bookId}/resume`,
  exportZh: (bookId) => `${API_BASE}/books/${bookId}/export/zh`,
  exportBilingual: (bookId) => `${API_BASE}/books/${bookId}/export/bilingual`,
  consistencyReport: (bookId) => `${API_BASE}/books/${bookId}/reports/consistency`,
};

boot();

function boot() {
  elements.apiBaseLabel.textContent = API_BASE;
  bindEvents();
  void loadProviderProfiles();

  const rememberedBookId = window.localStorage.getItem(STORAGE_KEY);
  const queryBookId = new URLSearchParams(window.location.search).get("bookId");
  const initialBookId = queryBookId || rememberedBookId;

  if (initialBookId) {
    elements.bookIdInput.value = initialBookId;
    void loadBook(initialBookId, { silent: false });
  } else {
    appendLog("系统已就绪，等待上传 EPUB 或加载现有书籍 ID。");
    render();
  }
}

function bindEvents() {
  elements.uploadForm.addEventListener("submit", onUploadSubmit);
  elements.lookupForm.addEventListener("submit", onLookupSubmit);
  elements.translationForm.addEventListener("submit", onTranslateSubmit);
  elements.translationProviderProfileSelect.addEventListener("change", onProviderProfileChange);
  elements.refreshButton.addEventListener("click", () => {
    if (state.currentBookId) {
      void loadBook(state.currentBookId, { silent: false });
    } else {
      appendLog("当前没有已加载的书籍。");
    }
  });
  elements.useLatestButton.addEventListener("click", () => {
    const rememberedBookId = window.localStorage.getItem(STORAGE_KEY);
    if (!rememberedBookId) {
      appendLog("没有找到已记忆的书籍 ID。");
      return;
    }
    elements.bookIdInput.value = rememberedBookId;
    void loadBook(rememberedBookId, { silent: false });
  });
  elements.stopPollingButton.addEventListener("click", () => {
    stopPolling();
    appendLog("已停止自动刷新。");
  });
  elements.resumeButton.addEventListener("click", () => {
    void resumeTranslation();
  });
  elements.downloadZhButton.addEventListener("click", () => {
    void downloadArtifact("zh");
  });
  elements.downloadBilingualButton.addEventListener("click", () => {
    void downloadArtifact("bilingual");
  });
  elements.downloadConsistencyButton.addEventListener("click", () => {
    void downloadArtifact("consistency_report");
  });
}

async function onUploadSubmit(event) {
  event.preventDefault();

  const fileInput = document.querySelector("#book-file");
  const titleInput = document.querySelector("#book-title");
  const languageInput = document.querySelector("#source-language");
  const file = fileInput.files?.[0];

  if (!file) {
    appendLog("请先选择一个 `.epub` 文件。");
    return;
  }

  setBusy(elements.uploadButton, true, "上传中...");
  appendLog(`开始上传 ${file.name}。`);

  try {
    const contentBase64 = await fileToBase64(file);
    const payload = {
      filename: file.name,
      title: titleInput.value.trim() || null,
      source_language: languageInput.value.trim() || "en",
      content: contentBase64,
      content_base64: contentBase64,
      content_encoding: "base64",
    };

    const response = await fetchJson(endpoint.createBook(), {
      method: "POST",
      body: JSON.stringify(payload),
    });

    const createdBookId = response.book_id;
    if (!createdBookId) {
      throw new Error("创建书籍的响应中缺少 `book_id`。");
    }

    appendLog(`上传完成，已创建书籍 #${createdBookId}。`);
    elements.bookIdInput.value = String(createdBookId);
    await loadBook(createdBookId, { silent: true });
  } catch (error) {
    appendLog(normalizeError(error, "上传失败。"));
  } finally {
    setBusy(elements.uploadButton, false, "上传并解析");
  }
}

async function onLookupSubmit(event) {
  event.preventDefault();
  const bookId = elements.bookIdInput.value.trim();
  if (!bookId) {
    appendLog("请输入书籍 ID。");
    return;
  }
  await loadBook(bookId, { silent: false });
}

async function onTranslateSubmit(event) {
  event.preventDefault();
  if (!state.currentBookId) {
    appendLog("请先加载一本书，再启动翻译。");
    return;
  }

  setBusy(elements.translateButton, true, "启动中...");
  appendLog(
    `开始翻译书籍 #${state.currentBookId}，将使用 ${describeSelectedProviderProfile()}。`
  );

  try {
    const response = await fetchJson(endpoint.startTranslation(state.currentBookId), {
      method: "POST",
      body: JSON.stringify(buildTranslationRequestPayload()),
    });

    appendLog(
      `翻译任务已启动，任务 #${response.job_id ?? "?"}，状态 ${translateStatus(response.status ?? "unknown")}。`
    );
    await loadBook(state.currentBookId, { silent: true });
    startPolling();
  } catch (error) {
    appendLog(normalizeError(error, "启动翻译失败。"));
  } finally {
    setBusy(elements.translateButton, false, "开始翻译");
  }
}

async function resumeTranslation() {
  if (!state.currentBookId) {
    appendLog("请先加载一本书，再恢复翻译。");
    return;
  }

  setBusy(elements.resumeButton, true, "恢复中...");
  appendLog(
    `尝试恢复书籍 #${state.currentBookId}，将使用 ${describeSelectedProviderProfile()}。`
  );

  try {
    const response = await fetchJson(endpoint.resumeTranslation(state.currentBookId), {
      method: "POST",
      body: JSON.stringify(buildTranslationRequestPayload()),
    });

    appendLog(
      `恢复请求已发送，任务 #${response.job_id ?? "?"}，状态 ${translateStatus(response.status ?? "unknown")}。`
    );
    await loadBook(state.currentBookId, { silent: true });
    startPolling();
  } catch (error) {
    appendLog(normalizeError(error, "恢复翻译失败。"));
  } finally {
    setBusy(elements.resumeButton, false, "恢复任务");
  }
}

async function loadBook(bookId, options = {}) {
  const normalizedBookId = String(bookId).trim();
  if (!normalizedBookId) {
    return;
  }

  if (!options.silent) {
    appendLog(`正在加载书籍 #${normalizedBookId}。`);
  }

  try {
    const response = await fetchJson(endpoint.getBook(normalizedBookId), {
      method: "GET",
    });

    state.currentBookId = Number(response.book?.id ?? normalizedBookId);
    state.currentBookDetail = response;

    window.localStorage.setItem(STORAGE_KEY, String(state.currentBookId));
    updateUrlBookId(state.currentBookId);
    render();

    appendLog(
      `已载入《${displayBookTitle(response.book) || "未命名"}》 (#${state.currentBookId})。`
    );

    if (shouldPoll(response.current_job)) {
      startPolling();
    } else {
      stopPolling();
    }
  } catch (error) {
    appendLog(normalizeError(error, `加载书籍 #${normalizedBookId} 失败。`));
  }
}

function render() {
  const detail = state.currentBookDetail;
  const book = detail?.book;
  const job = detail?.current_job;

  elements.currentBookLabel.textContent = book
    ? `#${book.id} · ${displayBookTitle(book)}`
    : "未选择";

  renderBookMetadata(book, job);
  renderJob(job, detail?.chapters ?? []);
  renderExports(detail?.artifacts ?? []);
  renderChapters(detail?.chapters ?? []);
  renderProviderProfileSummary();
  renderLog();

  elements.detailPanel.classList.toggle("is-empty", !book);
}

function renderBookMetadata(book, job) {
  if (!book) {
    elements.bookMetadata.innerHTML = `
      <div>
        <dt>状态</dt>
        <dd>请先载入或上传一本书。</dd>
      </div>
    `;
    return;
  }

  const createdAt = formatDateTime(book.created_at);
  const jobStatus = translateStatus(job?.status ?? "pending");
  const providerProfile = job?.provider_profile_name
    ? escapeHtml(job.provider_profile_name)
    : "未指定";
  const providerRuntime = [job?.provider_name, job?.model_name]
      .filter(Boolean)
      .map((value) => escapeHtml(value))
      .join(" / ") || "-";
  const translatedTitle = normalizedTranslatedTitle(book);
  const titleTranslationStatus = translateTitleTranslationStatus(
    book?.title_translation_status
  );

  elements.bookMetadata.innerHTML = `
    <div>
      <dt>当前显示标题</dt>
      <dd>${escapeHtml(displayBookTitle(book))}</dd>
    </div>
    <div>
      <dt>原标题</dt>
      <dd>${escapeHtml(book.title)}</dd>
    </div>
    <div>
      <dt>译后标题</dt>
      <dd>${escapeHtml(renderTranslatedTitle(book))}</dd>
    </div>
    <div>
      <dt>书名翻译</dt>
      <dd>${escapeHtml(titleTranslationStatus)}</dd>
    </div>
    <div>
      <dt>书籍 ID</dt>
      <dd>#${book.id}</dd>
    </div>
    <div>
      <dt>文件名</dt>
      <dd>${escapeHtml(book.filename)}</dd>
    </div>
    <div>
      <dt>源语言</dt>
      <dd>${escapeHtml(book.source_language)}</dd>
    </div>
    <div>
      <dt>创建时间</dt>
      <dd>${escapeHtml(createdAt)}</dd>
    </div>
    <div>
      <dt>当前任务</dt>
      <dd>${escapeHtml(jobStatus)}</dd>
    </div>
    <div>
      <dt>翻译配置档</dt>
      <dd>${providerProfile}</dd>
    </div>
    <div>
      <dt>Provider / Model</dt>
      <dd>${providerRuntime}</dd>
    </div>
  `;
}

function renderJob(job, chapters) {
  const totals = chapters.reduce(
    (accumulator, chapter) => {
      accumulator.total += chapter.total_segments;
      accumulator.translated += chapter.translated_segments;
      accumulator.failed += chapter.failed_segments;
      return accumulator;
    },
    { total: 0, translated: 0, failed: 0 }
  );
  const percentage = clampPercentage((job?.progress ?? progressFromChapters(totals)) * 100);
  const badge = statusBadgeClass(job?.status);

  elements.jobStatusPill.className = `status-pill ${badge}`;
  elements.jobStatusPill.textContent = translateStatus(job?.status ?? "idle");
  elements.jobProgressNumber.textContent = `${Math.round(percentage)}%`;
  elements.jobProgressBar.style.width = `${percentage}%`;
  elements.jobProgressLabel.textContent = job
    ? `已翻译 ${totals.translated}/${totals.total} 个段落`
    : "当前没有活动任务";
}

function renderExports(artifacts) {
  const byKind = new Map(artifacts.map((artifact) => [artifact.kind, artifact]));
  const cards = [
    renderExportCard("zh", "中文 EPUB", byKind.get("zh")),
    renderExportCard("bilingual", "中英双语 EPUB", byKind.get("bilingual")),
    renderExportCard("consistency_report", "一致性报告", byKind.get("consistency_report")),
  ];
  elements.exportList.innerHTML = cards.join("");
}

function renderExportCard(kind, label, artifact) {
  const status = translateStatus(artifact?.status ?? "pending");
  const sizeText = artifact?.size ? formatBytes(artifact.size) : "等待生成";

  return `
    <div class="export-card">
      <h3>${escapeHtml(label)}</h3>
      <p>状态：<strong>${escapeHtml(status)}</strong></p>
      <p>大小：<strong>${escapeHtml(sizeText)}</strong></p>
      <p>导出物 ID：<strong>${artifact?.id ?? "-"}</strong></p>
      <p>类型：<strong>${escapeHtml(translateArtifactKind(kind))}</strong></p>
    </div>
  `;
}

function renderChapters(chapters) {
  if (!chapters.length) {
    elements.chaptersList.innerHTML =
      '<div class="empty-state">载入书籍后，这里会显示章节进度。</div>';
    return;
  }

  elements.chaptersList.innerHTML = chapters
    .map((chapter) => {
      const total = chapter.total_segments || 0;
      const translated = chapter.translated_segments || 0;
      const failed = chapter.failed_segments || 0;
      const progress = total > 0 ? (translated / total) * 100 : 0;

      return `
        <article class="chapter-card">
          <div>
            <h3>${escapeHtml(chapter.title)}</h3>
            <div class="chapter-meta">
              <span>章节 #${chapter.order}</span>
              <span>失败：${failed}</span>
            </div>
          </div>
          <div class="mini-progress">
            <div class="progress-track">
              <div class="progress-bar" style="width:${clampPercentage(progress)}%"></div>
            </div>
            <strong>${translated}/${total}</strong>
          </div>
        </article>
      `;
    })
    .join("");
}

function renderLog() {
  if (!state.activity.length) {
    elements.messageLog.innerHTML =
      '<div class="empty-state">暂无活动记录。你的操作和服务端返回会显示在这里。</div>';
    return;
  }

  elements.messageLog.innerHTML = state.activity
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

async function loadProviderProfiles() {
  try {
    const response = await fetchJson(endpoint.listProviders(), {
      method: "GET",
    });
    state.providerProfiles = Array.isArray(response?.providers) ? response.providers : [];
    state.defaultProviderProfileName = String(
      response?.default_profile_name
      || state.providerProfiles[0]?.profile_name
      || state.providerProfiles[0]?.name
      || ""
    ).trim() || null;
    ensureSelectedProviderProfile();
    renderProviderProfileSummary();
    appendLog(
      state.providerProfiles.length
        ? `已加载 ${state.providerProfiles.length} 个翻译配置档，当前选择 ${describeSelectedProviderProfile()}。`
        : "后端没有返回可用的翻译配置档。"
    );
  } catch (error) {
    appendLog(normalizeError(error, "加载翻译配置档失败。"));
    renderProviderProfileSummary();
  }
}

function onProviderProfileChange(event) {
  state.selectedProviderProfileName = String(event.target.value || "").trim() || null;
  if (state.selectedProviderProfileName) {
    window.localStorage.setItem(PROVIDER_PROFILE_STORAGE_KEY, state.selectedProviderProfileName);
  } else {
    window.localStorage.removeItem(PROVIDER_PROFILE_STORAGE_KEY);
  }
  renderProviderProfileSummary();
  appendLog(`翻译配置档已切换为 ${describeSelectedProviderProfile()}。`);
}

function renderProviderProfileSummary() {
  const select = elements.translationProviderProfileSelect;
  const summary = elements.translationProviderSummary;
  const profiles = state.providerProfiles;

  if (!profiles.length) {
    select.disabled = true;
    select.innerHTML = '<option value="">未找到可用配置</option>';
    summary.textContent = "当前没有可用的翻译配置档。";
    return;
  }

  ensureSelectedProviderProfile();
  select.disabled = false;
  select.innerHTML = profiles
    .map((profile) => {
      const profileName = profileIdentifier(profile);
      const suffix = profile.is_default ? "（默认）" : "";
      return `<option value="${escapeHtml(profileName)}">${escapeHtml(profileName)}${suffix}</option>`;
    })
    .join("");
  select.value = state.selectedProviderProfileName || "";

  const selectedProfile = getSelectedProviderProfile();
  if (!selectedProfile) {
    summary.textContent = "请选择一个翻译配置档。";
    return;
  }

  const providerName = selectedProfile.provider_name || "-";
  const modelName = selectedProfile.default_model_name || "-";
  const configuredText = selectedProfile.configured ? "已配置" : "未配置";
  const rpmLimit = selectedProfile.max_requests_per_minute ?? "-";
  const globalConcurrency = selectedProfile.global_max_concurrency ?? "-";
  const perChapterConcurrency = selectedProfile.per_chapter_concurrency ?? "-";
  summary.textContent =
    `当前将使用配置档 ${profileIdentifier(selectedProfile)}，provider 为 ${providerName}，模型为 ${modelName}，RPM 上限 ${rpmLimit}，全局并发 ${globalConcurrency}，单章并发 ${perChapterConcurrency}，状态 ${configuredText}。`;
}

async function downloadArtifact(kind) {
  if (!state.currentBookId) {
    appendLog("请先加载书籍，再执行导出下载。");
    return;
  }

  const url = kind === "zh"
    ? endpoint.exportZh(state.currentBookId)
    : kind === "bilingual"
      ? endpoint.exportBilingual(state.currentBookId)
      : endpoint.consistencyReport(state.currentBookId);

  appendLog(`请求下载 ${translateArtifactKind(kind)}。`);

  try {
    const response = await fetch(url, {
      method: "GET",
      headers: {
        Accept: kind === "consistency_report"
          ? "application/json, text/markdown"
          : "application/epub+zip, application/json",
      },
    });

    const contentType = response.headers.get("content-type") || "";
    if (!response.ok) {
      if (contentType.includes("application/json")) {
        const payload = await response.json();
        throw new Error(payload.message || payload.detail || "下载失败。");
      }
      throw new Error(`下载失败，状态码 ${response.status}。`);
    }

    if (contentType.includes("application/json")) {
      if (kind === "consistency_report") {
        const payload = await response.json();
        const blob = new Blob([JSON.stringify(payload, null, 2)], {
          type: "application/json",
        });
        const objectUrl = window.URL.createObjectURL(blob);
        const anchor = document.createElement("a");
        anchor.href = objectUrl;
        anchor.download = `book-${state.currentBookId}-consistency-report.json`;
        document.body.append(anchor);
        anchor.click();
        anchor.remove();
        window.URL.revokeObjectURL(objectUrl);
        appendLog("一致性报告下载已开始。");
        return;
      }
      const payload = await response.json();
      const directPath = payload.path || payload.download_url || payload.url;

      if (directPath && (directPath.startsWith("/") || directPath.startsWith("http"))) {
        window.location.assign(directPath);
        appendLog(`导出已就绪，跳转到 ${directPath}。`);
        return;
      }

      if (directPath) {
        appendLog(`导出已就绪，但后端返回的是本地路径：${directPath}`);
        return;
      }

      window.location.assign(url);
      appendLog("后端返回 JSON，但未提供可直接访问的 URL，已尝试直接打开接口地址。");
      return;
    }

    if (kind === "consistency_report" && contentType.includes("text/markdown")) {
      const text = await response.text();
      const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
      const objectUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = objectUrl;
      anchor.download = `book-${state.currentBookId}-consistency-report.md`;
      document.body.append(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(objectUrl);
      appendLog("Markdown 一致性报告下载已开始。");
      return;
    }

    const blob = await response.blob();
    const filename = extractFilename(response.headers.get("content-disposition"))
      || (kind === "consistency_report" ? `${kind}.json` : `${kind}.epub`);
    const objectUrl = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = filename;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(objectUrl);
    appendLog(`导出下载已开始：${filename}。`);
  } catch (error) {
    appendLog(normalizeError(error, "导出下载失败。"));
  }
}

function appendLog(message) {
  const timestamp = new Date().toLocaleTimeString("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  });

  state.activity.unshift({
    time: timestamp,
    message,
  });
  renderLog();
}

function startPolling() {
  if (!state.currentBookId) {
    return;
  }
  stopPolling();
  state.pollTimer = window.setInterval(() => {
    void loadBook(state.currentBookId, { silent: true });
  }, POLL_INTERVAL_MS);
  elements.pollingLabel.textContent = `每 ${Math.round(POLL_INTERVAL_MS / 1000)} 秒`;
}

function stopPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
  elements.pollingLabel.textContent = "空闲";
}

function shouldPoll(job) {
  return Boolean(job && ["pending", "running"].includes(job.status));
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : null;

  if (!response.ok) {
    throw new Error(
      payload?.message
      || payload?.detail?.message
      || payload?.detail
      || `请求失败，状态码 ${response.status}。`
    );
  }

  return payload;
}

function progressFromChapters(totals) {
  if (!totals.total) {
    return 0;
  }
  return totals.translated / totals.total;
}

function setBusy(button, isBusy, label) {
  button.disabled = isBusy;
  if (isBusy) {
    button.dataset.originalLabel = button.textContent;
    button.textContent = label;
    return;
  }
  button.textContent = button.dataset.originalLabel || label;
}

function updateUrlBookId(bookId) {
  const url = new URL(window.location.href);
  url.searchParams.set("bookId", String(bookId));
  window.history.replaceState({}, "", url);
}

function normalizeError(error, fallback) {
  if (!error) {
    return fallback;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

function buildTranslationRequestPayload() {
  const selectedProfile = getSelectedProviderProfile();
  if (!selectedProfile) {
    return {};
  }
  return {
    provider: {
      profileName: profileIdentifier(selectedProfile),
    },
  };
}

function getSelectedProviderProfile() {
  ensureSelectedProviderProfile();
  return state.providerProfiles.find((profile) => {
    const profileName = profileIdentifier(profile);
    return profileName === state.selectedProviderProfileName;
  }) || null;
}

function ensureSelectedProviderProfile() {
  const availableProfiles = new Set(
    state.providerProfiles
      .map((profile) => profileIdentifier(profile))
      .filter(Boolean)
  );
  if (!availableProfiles.size) {
    state.selectedProviderProfileName = null;
    return;
  }

  const preferredProfileName = String(
    state.selectedProviderProfileName
    || state.defaultProviderProfileName
    || profileIdentifier(state.providerProfiles[0])
    || ""
  ).trim();
  state.selectedProviderProfileName = availableProfiles.has(preferredProfileName)
    ? preferredProfileName
    : [...availableProfiles][0];
  window.localStorage.setItem(PROVIDER_PROFILE_STORAGE_KEY, state.selectedProviderProfileName);
}

function describeSelectedProviderProfile() {
  const selectedProfile = getSelectedProviderProfile();
  if (!selectedProfile) {
    return "后端默认翻译配置";
  }
  const providerName = selectedProfile.provider_name || "-";
  const modelName = selectedProfile.default_model_name || "-";
  return `配置档 ${profileIdentifier(selectedProfile)}（${providerName} / ${modelName}）`;
}

function profileIdentifier(profile) {
  return String(profile?.profile_name || profile?.name || "").trim();
}

function statusBadgeClass(status) {
  switch ((status || "").toLowerCase()) {
    case "completed":
    case "ready":
      return "status-success";
    case "running":
      return "status-running";
    case "failed":
    case "error":
      return "status-failed";
    case "pending":
      return "status-accent";
    default:
      return "status-neutral";
  }
}

function translateStatus(status) {
  switch ((status || "").toLowerCase()) {
    case "completed":
    case "ready":
      return "已完成";
    case "running":
      return "进行中";
    case "failed":
    case "error":
      return "失败";
    case "pending":
      return "等待中";
    case "idle":
      return "空闲";
    case "unknown":
      return "未知";
    default:
      return status || "-";
  }
}

function translateArtifactKind(kind) {
  switch ((kind || "").toLowerCase()) {
    case "zh":
      return "中文 EPUB";
    case "bilingual":
      return "中英双语 EPUB";
    case "consistency_report":
      return "一致性报告";
    default:
      return kind || "-";
  }
}

function normalizedTranslatedTitle(book) {
  return String(book?.translated_title || "").trim();
}

function displayBookTitle(book) {
  const normalizedStatus = String(book?.title_translation_status || "").trim().toLowerCase();
  return normalizedStatus === "completed"
    ? normalizedTranslatedTitle(book) || String(book?.title || "").trim()
    : String(book?.title || "").trim();
}

function renderTranslatedTitle(book) {
  const normalizedStatus = String(book?.title_translation_status || "").trim().toLowerCase();
  const translatedTitle = normalizedTranslatedTitle(book);
  if (normalizedStatus === "completed") {
    return translatedTitle || "未生成";
  }
  if (normalizedStatus === "failed") {
    return "未生成";
  }
  return "待生成";
}

function translateTitleTranslationStatus(status) {
  const normalizedStatus = String(status || "").trim().toLowerCase();
  if (normalizedStatus === "completed") {
    return "已翻译";
  }
  if (normalizedStatus === "failed") {
    return "生成失败";
  }
  return "未翻译";
}

function extractFilename(contentDisposition) {
  if (!contentDisposition) {
    return null;
  }
  const match = /filename\*?=(?:UTF-8''|")?([^\";]+)/i.exec(contentDisposition);
  return match ? decodeURIComponent(match[1].replace(/"/g, "")) : null;
}

function clampPercentage(value) {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
}

function formatBytes(value) {
  if (!Number.isFinite(value) || value <= 0) {
    return "0 B";
  }
  const units = ["B", "KB", "MB", "GB"];
  let size = value;
  let index = 0;
  while (size >= 1024 && index < units.length - 1) {
    size /= 1024;
    index += 1;
  }
  return `${size.toFixed(size >= 10 || index === 0 ? 0 : 1)} ${units[index]}`;
}

function formatDateTime(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return date.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function fileToBase64(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result || "");
      const [, base64 = ""] = result.split(",", 2);
      resolve(base64);
    };
    reader.onerror = () => {
      reject(new Error(`无法读取文件 ${file.name}。`));
    };
    reader.readAsDataURL(file);
  });
}

