import { escapeHtml } from "./utils/html.js";
import { clampPercentage, formatBytes, formatDateTime, formatDuration, formatNumber } from "./utils/format.js";
import { bookStatusClass, statusBadgeClass, translateStatus } from "./utils/status.js";
import {
  bookCoverInitials,
  displayBookTitle,
  getBookCoverStyle,
  normalizedTranslatedTitle,
  renderTranslatedTitle,
  sourceLanguageLabel,
  translateArtifactKind,
} from "./utils/book.js";
import { createEndpoint, extractFilename, fetchJson, normalizeError } from "./api/index.js";
import { createElements } from "./dom.js";
import { normalizeRoute, renderRoute, syncRouteHash } from "./router.js";
import { createInitialState, FALLBACK_PROVIDER_PROFILES, POLL_INTERVAL_MS, PROVIDER_PROFILE_STORAGE_KEY, STORAGE_KEY } from "./state.js";
import { renderBookList, renderHome } from "./pages/home.js";
import { renderLog, renderTranslate } from "./pages/translate.js";
import {
  pickChapterId,
  pickReaderChapterId,
  pickReaderSegmentId,
  pickSegmentId,
  renderReader,
  renderReaderChapterOptions,
  renderReaderSegments,
  renderSegmentNotesPanel,
  getSelectedReaderSegment,
} from "./pages/reader.js";
import { bindEvents } from "./events.js";

// ==========================================
// CONSTANTS AND SINGLETONS
// ==========================================
const API_BASE = window.FANBOOK_API_BASE || "/api";
const state = createInitialState(window.localStorage);
const elements = createElements(document);
const endpoint = createEndpoint(API_BASE);

// ==========================================
// BOOT
// ==========================================
boot();

function boot() {
  elements.apiBaseLabel.textContent = API_BASE;
  state.activePage = normalizeRoute(window.location.hash);
  bindEvents({ elements, state, actions: createActions() });
  renderBookList({ elements, state });
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

  ensureRouteHash();
}

function createActions() {
  return {
    appendLog,
    applyRoute,
    cancelCurrentTranslation,
    downloadArtifact,
    downloadNotesExport,
    loadBook,
    loadReaderSegments,
    navigateTo,
    onBookListClick,
    onLookupSubmit,
    onProviderProfileChange,
    onReaderSegmentsClick,
    onTranslateSubmit,
    onUploadSubmit,
    renderBookList: () => renderBookList({ elements, state }),
    resumeTranslation,
    updateTranslatedTitle,
    useRememberedBook,
  };
}

// ==========================================
// ACTIONS AND FORM HANDLERS
// ==========================================
async function onBookListClick(event) {
  const row = event.target.closest("[data-book-id]");
  if (!row) {
    return;
  }
  const bookId = row.dataset.bookId;
  if (!bookId) {
    return;
  }
  elements.bookIdInput.value = bookId;
  await loadBook(bookId, { silent: false });
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
    elements.uploadForm.reset();
    const tip = document.querySelector("#upload-tip");
    if (tip) {
      tip.textContent = "上传 EPUB";
    }
    if (elements.uploadDropzone) {
      elements.uploadDropzone.style.borderColor = "";
    }
    await loadBooks({ silent: true });
    await loadBook(createdBookId, { silent: true });
    navigateTo("translate");
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
    render();
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
    render();
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
    render();
  }
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

async function downloadNotesExport() {
  if (!state.currentBookId) {
    appendLog("请先加载书籍，再导出笔记。");
    return;
  }

  appendLog(`请求导出书籍 #${state.currentBookId} 的笔记。`);

  try {
    const response = await fetch(endpoint.notesExport(state.currentBookId), {
      method: "GET",
      headers: {
        Accept: "text/markdown",
      },
    });

    const contentType = response.headers.get("content-type") || "";
    if (!response.ok) {
      if (contentType.includes("application/json")) {
        const payload = await response.json();
        throw new Error(payload.message || payload.detail || "导出失败。");
      }
      throw new Error(`导出失败，状态码 ${response.status}。`);
    }

    const text = await response.text();
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const objectUrl = window.URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = objectUrl;
    anchor.download = `book-${state.currentBookId}-notes.md`;
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    window.URL.revokeObjectURL(objectUrl);
    appendLog("笔记 Markdown 导出已开始。");
  } catch (error) {
    appendLog(normalizeError(error, "导出笔记失败。"));
  }
}

function onReaderSegmentsClick(event) {
  const noteButton = event.target.closest("[data-create-segment-note]");
  if (noteButton) {
    void createSegmentNote(noteButton.dataset.createSegmentNote);
    return;
  }
  const segment = event.target.closest("[data-reader-segment-id]");
  if (segment) {
    state.selectedReaderSegmentId = Number(segment.dataset.readerSegmentId) || null;
    void loadSegmentNotes(state.selectedReaderSegmentId);
  }
}

async function createSegmentNote(segmentId) {
  const normalizedSegmentId = Number(segmentId) || null;
  if (!normalizedSegmentId) {
    appendLog("请选择一个有效的段落后再创建笔记。");
    return;
  }

  const content = window.prompt("笔记内容", "");
  if (content === null) {
    return;
  }

  const trimmed = content.trim();
  if (!trimmed) {
    appendLog("笔记内容不能为空。");
    return;
  }

  try {
    await fetchJson(endpoint.segmentNotes(normalizedSegmentId), {
      method: "POST",
      body: JSON.stringify({
        content: trimmed,
        highlightColor: "#fff5db",
      }),
    });
    appendLog(`已为段落 #${normalizedSegmentId} 创建笔记。`);
    await loadSegmentNotes(normalizedSegmentId, { silent: true });
    if (state.currentBookId && state.selectedReaderChapterId) {
      await loadReaderSegments(state.currentBookId, state.selectedReaderChapterId, { silent: true });
    }
  } catch (error) {
    appendLog(normalizeError(error, "创建笔记失败。"));
  }
}

function useRememberedBook() {
  const rememberedBookId = window.localStorage.getItem(STORAGE_KEY);
  if (!rememberedBookId) {
    appendLog("没有找到已记忆的书籍 ID。");
    return;
  }
  elements.bookIdInput.value = rememberedBookId;
  void loadBook(rememberedBookId, { silent: false });
}

// ==========================================
// DATA LOADING
// ==========================================
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
    state.readerInfo = null;
    state.readerChapters = [];
    state.readerSegments = [];
    state.selectedReaderChapterId = null;
    state.selectedReaderSegmentId = null;
    state.selectedReaderNotes = [];

    window.localStorage.setItem(STORAGE_KEY, String(state.currentBookId));
    updateUrlBookId(state.currentBookId);
    render();
    await loadReader(state.currentBookId, { silent: options.silent });

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
    renderBookList({ elements, state });
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

async function loadReader(bookId, options = {}) {
  const normalizedBookId = Number(bookId) || null;
  if (!normalizedBookId) {
    state.readerInfo = null;
    state.readerChapters = [];
    state.readerSegments = [];
    state.selectedReaderChapterId = null;
    state.selectedReaderSegmentId = null;
    state.selectedReaderNotes = [];
    renderReaderChapterOptions({ elements, state, chapters: [] });
    renderReaderSegments({ elements, state });
    renderSegmentNotesPanel({ elements, state });
    return;
  }

  try {
    const [info, chaptersResponse] = await Promise.all([
      fetchJson(endpoint.readerInfo(normalizedBookId), { method: "GET" }),
      fetchJson(endpoint.readerChapters(normalizedBookId), { method: "GET" }),
    ]);

    state.readerInfo = info || null;
    state.readerChapters = Array.isArray(chaptersResponse?.chapters) ? chaptersResponse.chapters : [];
    state.selectedReaderChapterId = pickReaderChapterId(state.readerChapters, state.selectedReaderChapterId);
    renderReaderChapterOptions({ elements, state, chapters: state.readerChapters });

    if (state.selectedReaderChapterId) {
      await loadReaderSegments(normalizedBookId, state.selectedReaderChapterId, { silent: options.silent });
    } else {
      state.readerSegments = [];
      state.selectedReaderSegmentId = null;
      state.selectedReaderNotes = [];
      renderReaderSegments({ elements, state });
      renderSegmentNotesPanel({ elements, state });
    }
  } catch (error) {
    state.readerInfo = null;
    state.readerChapters = [];
    state.readerSegments = [];
    state.selectedReaderChapterId = null;
    state.selectedReaderSegmentId = null;
    state.selectedReaderNotes = [];
    renderReaderChapterOptions({ elements, state, chapters: [] });
    renderReaderSegments({ elements, state });
    renderSegmentNotesPanel({ elements, state });
    if (!options.silent) {
      appendLog(normalizeError(error, "加载阅读器内容失败。"));
    }
  }
}

async function loadReaderSegments(bookId, chapterId, options = {}) {
  const normalizedBookId = Number(bookId) || null;
  const normalizedChapterId = Number(chapterId) || null;
  if (!normalizedBookId || !normalizedChapterId) {
    state.readerSegments = [];
    state.selectedReaderSegmentId = null;
    state.selectedReaderNotes = [];
    renderReaderSegments({ elements, state });
    renderSegmentNotesPanel({ elements, state });
    return;
  }

  const mode = elements.readerMode?.value || state.selectedReaderMode || "bilingual";
  state.selectedReaderMode = mode;

  try {
    const response = await fetchJson(
      endpoint.readerSegments(normalizedBookId, normalizedChapterId, mode),
      { method: "GET" }
    );

    state.readerSegments = Array.isArray(response?.segments) ? response.segments : [];
    state.selectedReaderChapterId = Number(response?.chapterId ?? normalizedChapterId) || normalizedChapterId;
    state.selectedReaderSegmentId = pickReaderSegmentId(state.readerSegments, state.selectedReaderSegmentId);
    renderReaderSegments({ elements, state, response });

    if (state.selectedReaderSegmentId) {
      await loadSegmentNotes(state.selectedReaderSegmentId, { silent: true });
    } else {
      state.selectedReaderNotes = [];
      renderSegmentNotesPanel({ elements, state });
    }
  } catch (error) {
    state.readerSegments = [];
    state.selectedReaderSegmentId = null;
    state.selectedReaderNotes = [];
    renderReaderSegments({ elements, state });
    renderSegmentNotesPanel({ elements, state });
    if (!options.silent) {
      appendLog(normalizeError(error, "加载段落失败。"));
    }
  }
}

async function loadSegmentNotes(segmentId, options = {}) {
  const normalizedSegmentId = Number(segmentId) || null;
  if (!normalizedSegmentId) {
    state.selectedReaderNotes = [];
    renderSegmentNotesPanel({ elements, state });
    return;
  }

  try {
    const response = await fetchJson(endpoint.segmentNotes(normalizedSegmentId), {
      method: "GET",
    });
    state.selectedReaderSegmentId = normalizedSegmentId;
    state.selectedReaderNotes = Array.isArray(response) ? response : [];
    renderSegmentNotesPanel({ elements, state });
  } catch (error) {
    state.selectedReaderNotes = [];
    renderSegmentNotesPanel({ elements, state });
    if (!options.silent) {
      appendLog(normalizeError(error, "加载段落笔记失败。"));
    }
  }
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

// ==========================================
// RENDER ORCHESTRATION
// ==========================================
function render() {
  const detail = state.currentBookDetail;
  const book = detail?.book;
  const job = detail?.current_job;

  elements.currentBookLabel.textContent = book
    ? `${displayBookTitle(book)} · #${book.id}`
    : "未选择";

  const bigBookCover = document.querySelector("#book-cover");
  if (bigBookCover && book) {
    bigBookCover.style.background = getBookCoverStyle(book);
    const coverSpan = bigBookCover.querySelector("span");
    if (coverSpan) {
      coverSpan.textContent = bookCoverInitials(book);
    }
  }

  renderTranslate({
    elements,
    state,
    providerActions: {
      ensureSelectedProviderProfile,
      getSelectedProviderProfile,
      profileIdentifier,
    },
  });
  renderReader({ elements, state });
  renderHome({ elements, state });

  elements.detailPanel.classList.toggle("is-empty", !book);
  elements.readerPanel.classList.toggle("is-empty", !book);
  renderRoute(elements, state);
}

function applyRoute(hash) {
  const route = normalizeRoute(hash);
  syncRouteHash(route);
  if (state.activePage === route) {
    renderRoute(elements, state);
    return;
  }
  state.activePage = route;
  renderRoute(elements, state);
  render();
}

function navigateTo(route) {
  const normalized = normalizeRoute(`#/${route}`);
  window.location.hash = `#/${normalized}`;
}

function ensureRouteHash() {
  const route = normalizeRoute(window.location.hash);
  state.activePage = route;
  syncRouteHash(route);
  renderRoute(elements, state);
}

// ==========================================
// PROVIDER PROFILE STATE
// ==========================================
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

function renderProviderProfileSummary() {
  renderTranslate({
    elements,
    state,
    providerActions: {
      ensureSelectedProviderProfile,
      getSelectedProviderProfile,
      profileIdentifier,
    },
  });
}

// ==========================================
// POLLING
// ==========================================
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

// ==========================================
// SMALL DOM SIDE EFFECTS
// ==========================================
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

function setApiConnectionStatus(isConnected) {
  elements.apiConnectionLabel.innerHTML = `<span class="status-dot"></span>${isConnected ? "已连接" : "未连接"}`;
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
  renderLog({ elements, activity: state.activity });
}
