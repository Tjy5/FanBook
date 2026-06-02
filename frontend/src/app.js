const API_BASE = window.FANBOOK_API_BASE || "/api";
const STORAGE_KEY = "fanbook.currentBookId";
const PROVIDER_PROFILE_STORAGE_KEY = "fanbook.translationProviderProfile";
const POLL_INTERVAL_MS = 3000;

const state = {
  currentBookId: null,
  currentBookDetail: null,
  books: [],
  statusCounts: null,
  activeBookFilter: "all",
  pollTimer: null,
  activity: [
    { time: "14:35:21", message: "开始翻译: Book Three: The Prophet" },
    { time: "14:35:18", message: "API 请求成功 (tokens: 2,048)" },
    { time: "14:34:57", message: "段落翻译失败 (段落 ID: B3_0456)" },
    { time: "14:34:42", message: "重试成功 (段落 ID: B3_0456)" },
    { time: "14:33:58", message: "导出完成: 双语 EPUB (Dune_bilingual.epub)" },
  ],
  providerProfiles: [],
  defaultProviderProfileName: null,
  selectedProviderProfileName: window.localStorage.getItem(PROVIDER_PROFILE_STORAGE_KEY),
};

const DEMO_DETAIL = {
  book: {
    id: "fb_20240526_0001",
    title: "Dune",
    translated_title: "沙丘（暂未设置）",
    title_translation_status: "pending",
    filename: "Dune - Frank Herbert.epub",
    source_language: "en",
    created_at: "2024-05-26T14:32:18",
  },
  current_job: {
    status: "running",
    progress: 0.68,
    total_segments: 12843,
    translated_segments: 8734,
    failed_segments: 126,
    estimated_remaining_seconds: 8280,
    provider_profile_name: "默认配置",
    provider_name: "OpenAI",
    model_name: "gpt-4o",
  },
  chapters: [
    { order: 1, title: "Prologue", total_segments: 59, translated_segments: 59, failed_segments: 0 },
    { order: 2, title: "Book One: Dune", total_segments: 1484, translated_segments: 1484, failed_segments: 3 },
    { order: 3, title: "Book Two: Muad'dib", total_segments: 1752, translated_segments: 1201, failed_segments: 12 },
    { order: 4, title: "Book Three: The Prophet", total_segments: 2368, translated_segments: 1280, failed_segments: 28 },
    { order: 5, title: "Book Four: God Emperor of Dune", total_segments: 2105, translated_segments: 1012, failed_segments: 31 },
    { order: 6, title: "Book Five: Heretics of Dune", total_segments: 2317, translated_segments: 1095, failed_segments: 27 },
    { order: 7, title: "Book Six: Chapterhouse: Dune", total_segments: 1758, translated_segments: 603, failed_segments: 25 },
  ],
  artifacts: [
    { id: "zh-preview", kind: "zh", status: "pending", size: 0 },
    { id: "bilingual-preview", kind: "bilingual", status: "ready", size: 3982144 },
    { id: "consistency-preview", kind: "consistency_report", status: "ready", size: 18432 },
  ],
};

const FALLBACK_PROVIDER_PROFILES = [
  {
    profile_name: "默认配置",
    provider_name: "OpenAI",
    default_model_name: "gpt-4o",
    configured: true,
    max_requests_per_minute: 60,
    global_max_concurrency: 4,
    per_chapter_concurrency: 1,
    is_default: true,
  },
];

const elements = {
  apiBaseLabel: document.querySelector("#api-base-label"),
  apiConnectionLabel: document.querySelector("#api-connection-label"),
  providerStatusLabel: document.querySelector("#provider-status-label"),
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
  overallProgressRing: document.querySelector("#overall-progress-ring"),
  totalSegments: document.querySelector("#total-segments"),
  translatedSegments: document.querySelector("#translated-segments"),
  failedSegments: document.querySelector("#failed-segments"),
  remainingSegments: document.querySelector("#remaining-segments"),
  bookList: document.querySelector("#book-list"),
  libraryTabs: document.querySelector(".library-tabs"),
};

const endpoint = {
  createBook: () => `${API_BASE}/books`,
  listBooks: () => `${API_BASE}/books`,
  listProviders: () => `${API_BASE}/providers`,
  getBook: (bookId) => `${API_BASE}/books/${bookId}`,
  updateTranslatedTitle: (bookId) => `${API_BASE}/books/${bookId}/translated-title`,
  startTranslation: (bookId) => `${API_BASE}/books/${bookId}/translation-jobs`,
  resumeTranslation: (bookId) => `${API_BASE}/books/${bookId}/translation-jobs/resume`,
  cancelTranslation: (jobId) => `${API_BASE}/translation-jobs/${jobId}/cancel`,
  exportZh: (bookId) => `${API_BASE}/books/${bookId}/exports/zh`,
  exportBilingual: (bookId) => `${API_BASE}/books/${bookId}/exports/bilingual`,
  consistencyReport: (bookId) => `${API_BASE}/books/${bookId}/reports/consistency`,
};

boot();

function boot() {
  elements.apiBaseLabel.textContent = API_BASE;
  bindEvents();
  renderBookList();
  void loadBooks();
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
    void cancelCurrentTranslation();
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
  elements.bookList.addEventListener("click", (event) => {
    const row = event.target.closest("[data-book-id]");
    if (!row) {
      return;
    }
    elements.bookIdInput.value = row.dataset.bookId;
    void loadBook(row.dataset.bookId, { silent: false });
  });
  elements.libraryTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) {
      return;
    }
    state.activeBookFilter = button.dataset.filter;
    renderBookList();
  });
  elements.bookMetadata.addEventListener("click", (event) => {
    const button = event.target.closest("[data-edit-translated-title]");
    if (!button) {
      return;
    }
    void updateTranslatedTitle();
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
    const formData = new FormData();
    formData.append("file", file);
    formData.append("sourceLanguage", languageInput.value.trim() || "en");
    if (titleInput.value.trim()) {
      formData.append("title", titleInput.value.trim());
    }

    const response = await fetchJson(endpoint.createBook(), {
      method: "POST",
      body: formData,
    });

    const createdBookId = response.bookId;
    if (!createdBookId) {
      throw new Error("创建书籍的响应中缺少 `bookId`。");
    }

    appendLog(`上传完成，已创建书籍 #${createdBookId}。`);
    elements.bookIdInput.value = String(createdBookId);
    await loadBooks({ silent: true });
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
      `翻译任务已启动，任务 #${response.jobId ?? "?"}，状态 ${translateStatus(response.status ?? "unknown")}。`
    );
    await loadBook(state.currentBookId, { silent: true });
    await loadBooks({ silent: true });
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
      `恢复请求已发送，任务 #${response.jobId ?? "?"}，状态 ${translateStatus(response.status ?? "unknown")}。`
    );
    await loadBook(state.currentBookId, { silent: true });
    await loadBooks({ silent: true });
    startPolling();
  } catch (error) {
    appendLog(normalizeError(error, "恢复翻译失败。"));
  } finally {
    setBusy(elements.resumeButton, false, "恢复任务");
  }
}

async function cancelCurrentTranslation() {
  const jobId = state.currentBookDetail?.current_job?.job_id;
  if (!jobId) {
    stopPolling();
    appendLog("当前没有可取消的翻译任务，已停止自动刷新。");
    return;
  }

  setBusy(elements.stopPollingButton, true, "取消中...");
  try {
    const response = await fetchJson(endpoint.cancelTranslation(jobId), {
      method: "POST",
    });
    stopPolling();
    appendLog(`已取消任务 #${response.jobId ?? jobId}，状态 ${translateStatus(response.status ?? "unknown")}。`);
    if (state.currentBookId) {
      await loadBook(state.currentBookId, { silent: true });
      await loadBooks({ silent: true });
    }
  } catch (error) {
    appendLog(normalizeError(error, "取消任务失败。"));
  } finally {
    setBusy(elements.stopPollingButton, false, "取消当前任务");
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

async function loadBooks(options = {}) {
  try {
    const response = await fetchJson(endpoint.listBooks(), {
      method: "GET",
    });
    state.books = Array.isArray(response?.books) ? response.books : [];
    state.statusCounts = response?.status_counts || null;
    renderBookList();
    if (!options.silent) {
      appendLog(`已加载 ${state.books.length} 本书籍。`);
    }
    setApiConnectionStatus(true);
  } catch (error) {
    setApiConnectionStatus(false);
    if (!options.silent) {
      appendLog(normalizeError(error, "加载书籍列表失败。"));
    }
  }
}

function render() {
  const detail = state.currentBookDetail || DEMO_DETAIL;
  const book = detail?.book;
  const job = detail?.current_job;
  const isPreview = !state.currentBookDetail;

  elements.currentBookLabel.textContent = book
    ? `${displayBookTitle(book)}${isPreview ? "" : ` · #${book.id}`}`
    : "未选择";

  renderBookMetadata(book, job, { isPreview });
  renderJob(job, detail?.chapters ?? []);
  renderExports(detail?.artifacts ?? []);
  renderChapters(detail?.chapters ?? [], job);
  renderBookList();
  renderProviderProfileSummary();
  renderLog();

  elements.detailPanel.classList.toggle("is-empty", !book);
}

function renderBookMetadata(book, job, options = {}) {
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
  const translatedTitle = options.isPreview
    ? book.translated_title
    : renderTranslatedTitle(book);
  const sourceLanguage = sourceLanguageLabel(book.source_language);

  elements.bookMetadata.innerHTML = `
    <div>
      <dt>原标题</dt>
      <dd>${escapeHtml(book.title)}</dd>
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

function renderBookList() {
  renderLibraryTabs();
  if (!state.books.length) {
    elements.bookList.innerHTML =
      '<div class="empty-state">暂无书籍。上传 EPUB 后会出现在这里。</div>';
    return;
  }

  const filteredBooks = state.books.filter((book) => {
    if (state.activeBookFilter === "all") {
      return true;
    }
    return String(book.status || "").toLowerCase() === state.activeBookFilter;
  });

  if (!filteredBooks.length) {
    elements.bookList.innerHTML =
      '<div class="empty-state">当前筛选下没有书籍。</div>';
    return;
  }

  elements.bookList.innerHTML = filteredBooks
    .map((book) => {
      const status = String(book.status || "pending").toLowerCase();
      const activeClass = Number(book.id) === Number(state.currentBookId) ? " active" : "";
      return `
        <article class="book-row${activeClass}" data-book-id="${escapeHtml(book.id)}" role="button" tabindex="0">
          <div class="mini-cover" aria-hidden="true"><span>${escapeHtml(bookCoverInitials(book))}</span></div>
          <div>
            <h2>${escapeHtml(displayBookTitle(book) || "未命名书籍")}</h2>
            <p>${escapeHtml(book.filename || "-")}</p>
            <span>${escapeHtml(sourceLanguageLabel(book.source_language))} → 中文</span>
          </div>
          <time>${escapeHtml(formatDateTime(book.updated_at || book.created_at))}</time>
          <strong class="book-status ${bookStatusClass(status)}">${escapeHtml(translateStatus(status))}</strong>
        </article>
      `;
    })
    .join("");
}

function renderLibraryTabs() {
  const counts = state.statusCounts || countBooksByStatus(state.books);
  const tabs = [
    ["all", "全部", counts.total],
    ["running", "进行中", counts.running],
    ["completed", "已完成", counts.completed],
    ["failed", "失败", counts.failed],
  ];
  elements.libraryTabs.innerHTML = tabs
    .map(([filter, label, count]) => {
      const activeClass = state.activeBookFilter === filter ? " active" : "";
      return `<button class="tab-button${activeClass}" type="button" data-filter="${filter}">${label} <span>${formatNumber(count)}</span></button>`;
    })
    .join("");
}

function countBooksByStatus(books) {
  return books.reduce(
    (counts, book) => {
      counts.total += 1;
      const status = String(book.status || "").toLowerCase();
      if (status === "running") {
        counts.running += 1;
      } else if (status === "completed") {
        counts.completed += 1;
      } else if (status === "failed") {
        counts.failed += 1;
      }
      return counts;
    },
    { total: 0, running: 0, completed: 0, failed: 0 }
  );
}

function renderJob(job, chapters) {
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
    <article>
      <strong>${escapeHtml(label)}</strong>
      <span>${escapeHtml(status)} · ${escapeHtml(sizeText)}</span>
    </article>
  `;
}

function renderChapters(chapters, job) {
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
    setApiConnectionStatus(true);
    appendLog(
      state.providerProfiles.length
        ? `已加载 ${state.providerProfiles.length} 个翻译配置档，当前选择 ${describeSelectedProviderProfile()}。`
        : "后端没有返回可用的翻译配置档。"
    );
  } catch (error) {
    state.providerProfiles = FALLBACK_PROVIDER_PROFILES;
    state.defaultProviderProfileName = FALLBACK_PROVIDER_PROFILES[0].profile_name;
    ensureSelectedProviderProfile();
    renderProviderProfileSummary();
    setApiConnectionStatus(false);
    appendLog(`${normalizeError(error, "加载翻译配置档失败。")} 已使用本地预览配置。`);
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
    elements.providerStatusLabel.textContent = "不可用";
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
    `当前将使用配置档 ${profileIdentifier(selectedProfile)}，provider 为 ${providerName}，模型为 ${modelName}，RPM 上限 ${rpmLimit}，全局并发 ${globalConcurrency}，单章并发 ${perChapterConcurrency}，状态 ${configuredText}。`;
}

async function updateTranslatedTitle() {
  if (!state.currentBookId || !state.currentBookDetail?.book) {
    appendLog("请先加载一本书，再编辑译后标题。");
    return;
  }

  const currentValue = normalizedTranslatedTitle(state.currentBookDetail.book);
  const nextValue = window.prompt("译后标题", currentValue);
  if (nextValue === null) {
    return;
  }

  try {
    const response = await fetchJson(endpoint.updateTranslatedTitle(state.currentBookId), {
      method: "PATCH",
      body: JSON.stringify({
        translated_title: nextValue.trim(),
      }),
    });
    state.currentBookDetail = response;
    appendLog(`译后标题已更新为「${nextValue.trim() || "未设置"}」。`);
    await loadBooks({ silent: true });
    render();
  } catch (error) {
    appendLog(normalizeError(error, "更新译后标题失败。"));
  }
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
  const isFormData = options.body instanceof FormData;
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
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

function totalsFromJob(job, fallbackTotals) {
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

function estimateRemainingTime(job, totals, percentage) {
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

  const secondsPerSegment = state.currentBookDetail ? 2.2 : 2.08;
  return formatDuration(Math.round(remaining * secondsPerSegment));
}

function formatDuration(totalSeconds) {
  const minutes = Math.max(1, Math.round(totalSeconds / 60));
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  if (!hours) {
    return `${restMinutes} 分钟`;
  }
  if (!restMinutes) {
    return `${hours} 小时`;
  }
  return `${hours} 小时 ${restMinutes} 分钟`;
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(Number(value) || 0);
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
    providerName: selectedProfile.provider_name || profileIdentifier(selectedProfile),
    modelName: selectedProfile.default_model_name || null,
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

function sourceLanguageLabel(value) {
  const normalized = String(value || "").trim();
  if (!normalized) {
    return "-";
  }
  if (normalized.toLowerCase() === "en") {
    return "英文 (en)";
  }
  if (normalized.toLowerCase() === "zh") {
    return "中文 (zh)";
  }
  return normalized;
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
    case "queued":
      return "等待中";
    case "canceled":
      return "已取消";
    case "idle":
      return "空闲";
    case "unknown":
      return "未知";
    default:
      return status || "-";
  }
}

function bookStatusClass(status) {
  switch ((status || "").toLowerCase()) {
    case "running":
    case "pending":
      return "running";
    case "completed":
      return "done";
    case "failed":
      return "failed";
    default:
      return "running";
  }
}

function bookCoverInitials(book) {
  const title = displayBookTitle(book) || book?.filename || "FB";
  return String(title).trim().slice(0, 2).toUpperCase();
}

function setApiConnectionStatus(isConnected) {
  elements.apiConnectionLabel.innerHTML = `<span class="status-dot"></span>${isConnected ? "已连接" : "未连接"}`;
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

