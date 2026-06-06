import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  Archive,
  BookMarked,
  BookOpen,
  BookText,
  CheckCircle2,
  Download,
  FileText,
  Gauge,
  Languages,
  LibraryBig,
  LogOut,
  NotebookPen,
  Play,
  RefreshCw,
  RotateCcw,
  ScrollText,
  Settings,
  Shield,
  KeyRound,
  ServerCog,
  UploadCloud,
  UserRoundPlus,
  UsersRound,
  XCircle,
} from "lucide-react";
import { ApiClient, extractFilename, normalizeError } from "./api/client";
import type {
  AdminUser,
  BookDetail,
  BookListItem,
  ChapterSummary,
  CurrentUser,
  ExportArtifact,
  ProviderProfile,
  ReaderSegment,
  Role,
  SegmentNote,
  StatusCounts,
  TranslationJob,
} from "./types";
import { formatBytes, formatDateTime, formatDuration, formatNumber } from "./utils/format";
import {
  bookCoverInitials,
  displayBookTitle,
  getBookCoverStyle,
  normalizedTranslatedTitle,
  renderTranslatedTitle,
  sourceLanguageLabel,
  translateArtifactKind,
} from "./utils/book";
import { statusBadgeClass, translateStatus } from "./utils/status";
import "./styles.css";

const API_BASE = window.FANBOOK_API_BASE || "/api";
const STORAGE_KEY = "fanbook.currentBookId";
const PROVIDER_PROFILE_STORAGE_KEY = "fanbook.translationProviderProfile";
const POLL_INTERVAL_MS = 3000;
const EMPTY_COUNTS: StatusCounts = { total: 0, running: 0, completed: 0, failed: 0 };
const DEMO_BOOK_ID = -1;
const DEMO_BOOK_STORAGE_VALUE = "demo";
const DEMO_BOOK_UPDATED_AT = "2026-06-06T09:30:00Z";

const DEMO_BOOK_LIST_ITEM: BookListItem = {
  id: DEMO_BOOK_ID,
  title: "Fanbook Demo: The Translator's Desk",
  translated_title: "Fanbook 演示书：译者书桌",
  title_translation_status: "completed",
  filename: "fanbook-demo.epub",
  source_language: "en",
  status: "completed",
  progress: 1,
  total_segments: 8,
  translated_segments: 8,
  failed_segments: 0,
  current_job_status: "completed",
  created_at: DEMO_BOOK_UPDATED_AT,
  updated_at: DEMO_BOOK_UPDATED_AT,
};

const DEMO_BOOK_DETAIL: BookDetail = {
  book: {
    id: DEMO_BOOK_ID,
    title: DEMO_BOOK_LIST_ITEM.title,
    translated_title: DEMO_BOOK_LIST_ITEM.translated_title,
    title_translation_status: "completed",
    filename: DEMO_BOOK_LIST_ITEM.filename,
    source_language: DEMO_BOOK_LIST_ITEM.source_language,
    status: DEMO_BOOK_LIST_ITEM.status,
    created_at: DEMO_BOOK_UPDATED_AT,
    updated_at: DEMO_BOOK_UPDATED_AT,
  },
  current_job: {
    job_id: DEMO_BOOK_ID,
    book_id: DEMO_BOOK_ID,
    status: "completed",
    provider_profile_name: "fanbook-demo",
    provider_name: "fanbook",
    model_name: "demo-translator",
    progress: 1,
    total_segments: 8,
    translated_segments: 8,
    failed_segments: 0,
    estimated_remaining_seconds: 0,
    created_at: DEMO_BOOK_UPDATED_AT,
    updated_at: DEMO_BOOK_UPDATED_AT,
  },
  chapters: [
    { id: -101, chapterOrder: 1, title: "Before the Upload", total_segments: 4, translated_segments: 4, failed_segments: 0, progress: 1 },
    { id: -102, chapterOrder: 2, title: "Reading in Two Voices", total_segments: 4, translated_segments: 4, failed_segments: 0, progress: 1 },
  ],
  artifacts: [
    { id: -1, kind: "zh", status: "ready", filename: "fanbook-demo.zh.epub", size: 128000, created_at: DEMO_BOOK_UPDATED_AT },
    { id: -2, kind: "bilingual", status: "ready", filename: "fanbook-demo.bilingual.epub", size: 176000, created_at: DEMO_BOOK_UPDATED_AT },
    { id: -3, kind: "consistency_report", status: "ready", filename: "fanbook-demo.consistency.json", size: 4200, created_at: DEMO_BOOK_UPDATED_AT },
  ],
};

const DEMO_READER_SEGMENTS: Record<number, ReaderSegment[]> = {
  [-101]: [
    {
      id: -1001,
      order: 1,
      type: "paragraph",
      source_text: "Mira opened Fanbook before choosing a book of her own.",
      translated_text: "米拉在选择自己的书之前，先打开了 Fanbook。",
      translation_status: "completed",
      note_count: 1,
    },
    {
      id: -1002,
      order: 2,
      type: "paragraph",
      source_text: "The demo showed her what a chapter looks like after translation, without asking for an API key first.",
      translated_text: "演示书先让她看到章节翻译后的样子，而不是一开始就索要 API Key。",
      translation_status: "completed",
      note_count: 0,
    },
    {
      id: -1003,
      order: 3,
      type: "paragraph",
      source_text: "Every paragraph kept its source text beside the translated text, so uncertainty stayed visible.",
      translated_text: "每个段落都把原文和译文并排保留下来，让不确定之处仍然可见。",
      translation_status: "completed",
      note_count: 1,
    },
    {
      id: -1004,
      order: 4,
      type: "paragraph",
      source_text: "When she was ready, her own EPUB would join the private shelf.",
      translated_text: "等她准备好之后，自己的 EPUB 就会加入私人书架。",
      translation_status: "completed",
      note_count: 0,
    },
  ],
  [-102]: [
    {
      id: -2001,
      order: 1,
      type: "paragraph",
      source_text: "In bilingual mode, the rhythm of the original remained close enough to question the translation.",
      translated_text: "在双语模式里，原文的节奏仍然贴得很近，足以让读者质疑译文。",
      translation_status: "completed",
      note_count: 0,
    },
    {
      id: -2002,
      order: 2,
      type: "paragraph",
      source_text: "In translated mode, the page became quiet and continuous.",
      translated_text: "切到译文模式时，页面变得安静而连贯。",
      translation_status: "completed",
      note_count: 0,
    },
    {
      id: -2003,
      order: 3,
      type: "paragraph",
      source_text: "Notes belonged to the reader, but this demo kept them as examples only.",
      translated_text: "笔记属于读者自己，不过这本演示书只保留示例笔记。",
      translation_status: "completed",
      note_count: 1,
    },
    {
      id: -2004,
      order: 4,
      type: "paragraph",
      source_text: "The next real action was simple: upload a book, choose a model, and start reading.",
      translated_text: "下一步真实动作很简单：上传一本书，选择模型，然后开始阅读。",
      translation_status: "completed",
      note_count: 0,
    },
  ],
};

const DEMO_SEGMENT_NOTES: Record<number, SegmentNote[]> = {
  [-1001]: [
    { id: -1, segmentId: -1001, content: "演示书展示的是产品阅读体验，不占用用户私人书架。", created_by: "Fanbook", created_at: DEMO_BOOK_UPDATED_AT },
  ],
  [-1003]: [
    { id: -2, segmentId: -1003, content: "双语阅读要让原文和译文的差异可以被看见。", created_by: "Fanbook", created_at: DEMO_BOOK_UPDATED_AT },
  ],
  [-2003]: [
    { id: -3, segmentId: -2003, content: "真实用户笔记后续应继续按用户隔离保存。", created_by: "Fanbook", created_at: DEMO_BOOK_UPDATED_AT },
  ],
};

type Route = "library" | "translate" | "read" | "settings" | "admin-users";
type Filter = "all" | "running" | "completed" | "failed";
type ReaderMode = "bilingual" | "original" | "translated";
type ArtifactKind = "zh" | "bilingual" | "consistency_report";

interface ActivityEntry {
  time: string;
  message: string;
}

function App() {
  const api = useMemo(() => new ApiClient(API_BASE), []);
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null);
  const [authChecked, setAuthChecked] = useState(false);
  const [loginUsername, setLoginUsername] = useState("");
  const [loginPassword, setLoginPassword] = useState("");
  const [route, setRoute] = useState<Route>(() => normalizeRoute(window.location.hash));
  const [books, setBooks] = useState<BookListItem[]>([]);
  const [statusCounts, setStatusCounts] = useState<StatusCounts>(EMPTY_COUNTS);
  const [activeBookFilter, setActiveBookFilter] = useState<Filter>("all");
  const [currentBookId, setCurrentBookId] = useState<number | null>(null);
  const [bookDetail, setBookDetail] = useState<BookDetail | null>(null);
  const [bookIdInput, setBookIdInput] = useState("");
  const [providerProfiles, setProviderProfiles] = useState<ProviderProfile[]>([]);
  const [selectedProviderProfileName, setSelectedProviderProfileName] = useState<string | null>(
    localStorage.getItem(PROVIDER_PROFILE_STORAGE_KEY)
  );
  const [readerChapters, setReaderChapters] = useState<ChapterSummary[]>([]);
  const [selectedReaderChapterId, setSelectedReaderChapterId] = useState<number | null>(null);
  const [readerMode, setReaderMode] = useState<ReaderMode>("bilingual");
  const [readerSegments, setReaderSegments] = useState<ReaderSegment[]>([]);
  const [selectedReaderSegmentId, setSelectedReaderSegmentId] = useState<number | null>(null);
  const [segmentNotes, setSegmentNotes] = useState<SegmentNote[]>([]);
  const [activity, setActivity] = useState<ActivityEntry[]>([]);
  const [polling, setPolling] = useState(false);
  const [busyAction, setBusyAction] = useState<string | null>(null);
  const [adminUsers, setAdminUsers] = useState<AdminUser[]>([]);
  const [newUser, setNewUser] = useState({ username: "", password: "", email: "", role: "MEMBER" as Role });
  const pollTimer = useRef<number | null>(null);
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const titleInputRef = useRef<HTMLInputElement | null>(null);
  const languageInputRef = useRef<HTMLInputElement | null>(null);

  const isAdmin = hasRole(currentUser, "ADMIN");
  const isMemberLike = hasAnyRole(currentUser, ["ADMIN", "MEMBER"]);
  const selectedProviderProfile = useMemo(
    () => pickProvider(providerProfiles, selectedProviderProfileName),
    [providerProfiles, selectedProviderProfileName]
  );

  useEffect(() => {
    const onHashChange = () => setRoute(normalizeRoute(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    void bootstrapAuth();
  }, []);

  useEffect(() => {
    if (!currentUser) {
      return;
    }
    void loadBooks({ silent: true });
    void loadProviders();
    const requestedBookId = new URL(window.location.href).searchParams.get("bookId");
    const remembered = requestedBookId || localStorage.getItem(STORAGE_KEY);
    if (remembered) {
      setBookIdInput(remembered);
      void loadBook(bookIdFromStorage(remembered), { silent: true });
    } else {
      appendLog("系统已就绪，可以打开演示书或上传自己的 EPUB。");
    }
  }, [currentUser]);

  useEffect(() => {
    if (!bookDetail?.current_job) {
      stopPolling();
      return;
    }
    const status = String(bookDetail.current_job.status || "").toLowerCase();
    if (["pending", "queued", "running"].includes(status)) {
      startPolling();
      return;
    }
    stopPolling();
  }, [bookDetail?.current_job?.status, currentBookId]);

  useEffect(() => {
    return () => stopPolling();
  }, []);

  useEffect(() => {
    if (isAdmin && route === "admin-users") {
      void loadAdminUsers();
    }
  }, [isAdmin, route]);

  useEffect(() => {
    if (currentUser && route === "admin-users" && !isAdmin) {
      window.location.hash = "#/library";
      setRoute("library");
    }
  }, [currentUser, isAdmin, route]);

  async function bootstrapAuth() {
    try {
      await api.csrf();
      const user = await api.me();
      setCurrentUser(user);
      appendLog(`已登录为 ${user.username}。`);
    } catch {
      setCurrentUser(null);
    } finally {
      setAuthChecked(true);
    }
  }

  async function login(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("login");
    try {
      const user = await api.login({ username: loginUsername.trim(), password: loginPassword });
      setCurrentUser(user);
      setLoginPassword("");
      appendLog(`已登录为 ${user.username}。`);
    } catch (error) {
      appendLog(normalizeError(error, "登录失败。"));
    } finally {
      setBusyAction(null);
    }
  }

  async function logout() {
    setBusyAction("logout");
    try {
      await api.logout();
      setCurrentUser(null);
      setBookDetail(null);
      setCurrentBookId(null);
      setBooks([]);
      stopPolling();
    } catch (error) {
      appendLog(normalizeError(error, "退出登录失败。"));
    } finally {
      setBusyAction(null);
    }
  }

  async function loadBooks(options: { silent?: boolean } = {}) {
    try {
      const response = await api.listBooks();
      setBooks(response.books || []);
      setStatusCounts(response.status_counts || EMPTY_COUNTS);
      if (!options.silent) {
        appendLog(`已加载 ${response.books?.length || 0} 本书籍。`);
      }
    } catch (error) {
      if (!options.silent) {
        appendLog(normalizeError(error, "加载书籍列表失败。"));
      }
    }
  }

  async function loadProviders() {
    try {
      const response = await api.listProviders();
      const providers = response.providers || [];
      setProviderProfiles(providers);
      const preferred = selectedProviderProfileName || response.default_profile_name || providers[0]?.profile_name || null;
      if (preferred) {
        setSelectedProviderProfileName(preferred);
        localStorage.setItem(PROVIDER_PROFILE_STORAGE_KEY, preferred);
      }
    } catch (error) {
      appendLog(normalizeError(error, "加载翻译配置档失败。"));
    }
  }

  async function loadBook(bookId: number, options: { silent?: boolean } = {}) {
    if (isDemoBookId(bookId)) {
      await loadDemoBook(options);
      return;
    }
    if (!Number.isFinite(bookId) || bookId <= 0) {
      appendLog("请输入有效的书籍 ID。");
      return;
    }
    try {
      if (!options.silent) {
        appendLog(`正在加载书籍 #${bookId}。`);
      }
      const detail = await api.getBook(bookId);
      setBookDetail(detail);
      setCurrentBookId(detail.book.id);
      setBookIdInput(String(detail.book.id));
      localStorage.setItem(STORAGE_KEY, String(detail.book.id));
      updateBookIdSearch(detail.book.id);
      await loadReader(detail.book.id, { preserveSelection: false });
      if (!options.silent) {
        appendLog(`已载入《${displayBookTitle(detail.book) || "未命名"}》。`);
      }
    } catch (error) {
      appendLog(normalizeError(error, `加载书籍 #${bookId} 失败。`));
    }
  }

  async function loadDemoBook(options: { silent?: boolean } = {}) {
    const detail = cloneDemoBookDetail();
    setBookDetail(detail);
    setCurrentBookId(DEMO_BOOK_ID);
    setBookIdInput(DEMO_BOOK_STORAGE_VALUE);
    localStorage.setItem(STORAGE_KEY, DEMO_BOOK_STORAGE_VALUE);
    updateBookIdSearch(DEMO_BOOK_ID);
    await loadReader(DEMO_BOOK_ID, { preserveSelection: false });
    if (!options.silent) {
      appendLog("已打开 Fanbook 演示书。");
    }
  }

  async function openDemoBook(nextRoute?: Route) {
    await loadBook(DEMO_BOOK_ID);
    if (nextRoute) {
      navigateTo(nextRoute);
    }
  }

  async function loadReader(bookId: number, options: { preserveSelection?: boolean } = {}) {
    if (isDemoBookId(bookId)) {
      const chapters = cloneDemoBookDetail().chapters;
      setReaderChapters(chapters);
      const nextChapterId = pickReaderChapterId(chapters, options.preserveSelection ? selectedReaderChapterId : null);
      setSelectedReaderChapterId(nextChapterId);
      if (nextChapterId) {
        await loadReaderSegments(bookId, nextChapterId, readerMode, options.preserveSelection);
      }
      return;
    }
    try {
      const chaptersResponse = await api.readerChapters(bookId);
      const chapters = chaptersResponse.chapters || [];
      setReaderChapters(chapters);
      const nextChapterId = pickReaderChapterId(chapters, options.preserveSelection ? selectedReaderChapterId : null);
      setSelectedReaderChapterId(nextChapterId);
      if (nextChapterId) {
        await loadReaderSegments(bookId, nextChapterId, readerMode, options.preserveSelection);
      } else {
        setReaderSegments([]);
        setSelectedReaderSegmentId(null);
        setSegmentNotes([]);
      }
    } catch (error) {
      appendLog(normalizeError(error, "加载阅读器内容失败。"));
    }
  }

  async function loadReaderSegments(bookId: number, chapterId: number, mode: ReaderMode, preserveSelection = true) {
    if (isDemoBookId(bookId)) {
      const segments = cloneDemoReaderSegments(chapterId);
      setReaderSegments(segments);
      const nextSegmentId = pickReaderSegmentId(segments, preserveSelection ? selectedReaderSegmentId : null);
      setSelectedReaderSegmentId(nextSegmentId);
      if (nextSegmentId) {
        await loadSegmentNotes(nextSegmentId);
      } else {
        setSegmentNotes([]);
      }
      return;
    }
    try {
      const response = await api.readerSegments(bookId, chapterId, mode);
      const segments = response.segments || [];
      setReaderSegments(segments);
      const nextSegmentId = pickReaderSegmentId(segments, preserveSelection ? selectedReaderSegmentId : null);
      setSelectedReaderSegmentId(nextSegmentId);
      if (nextSegmentId) {
        await loadSegmentNotes(nextSegmentId);
      } else {
        setSegmentNotes([]);
      }
    } catch (error) {
      appendLog(normalizeError(error, "加载段落失败。"));
    }
  }

  async function loadSegmentNotes(segmentId: number) {
    if (isDemoSegmentId(segmentId)) {
      setSegmentNotes(cloneDemoSegmentNotes(segmentId));
      return;
    }
    try {
      const notes = await api.segmentNotes(segmentId);
      setSegmentNotes(notes || []);
    } catch (error) {
      appendLog(normalizeError(error, "加载段落笔记失败。"));
    }
  }

  async function uploadBook(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isMemberLike) {
      appendLog("当前角色没有上传权限。");
      return;
    }
    const file = fileInputRef.current?.files?.[0];
    if (!file) {
      appendLog("请先选择一个 `.epub` 文件。");
      return;
    }
    setBusyAction("upload");
    try {
      const formData = new FormData();
      formData.append("file", file);
      formData.append("sourceLanguage", languageInputRef.current?.value.trim() || "en");
      const title = titleInputRef.current?.value.trim();
      if (title) {
        formData.append("title", title);
      }
      const created = await api.uploadBook(formData);
      appendLog(`上传完成，已创建书籍 #${created.bookId}。`);
      event.currentTarget.reset();
      await loadBooks({ silent: true });
      await loadBook(created.bookId, { silent: true });
      navigateTo("translate");
    } catch (error) {
      appendLog(normalizeError(error, "上传失败。"));
    } finally {
      setBusyAction(null);
    }
  }

  async function startTranslation(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (isDemoBookId(currentBookId)) {
      appendLog("演示书是内置样例，不需要启动翻译任务。");
      return;
    }
    if (!currentBookId || !isMemberLike) {
      appendLog("请先加载书籍，并确认当前角色有翻译权限。");
      return;
    }
    setBusyAction("translate");
    try {
      const payload = translationPayload(selectedProviderProfile);
      const response = await api.startTranslation(currentBookId, payload);
      appendLog(`翻译任务已启动，任务 #${jobIdOf(response) ?? "?"}。`);
      await loadBook(currentBookId, { silent: true });
      await loadBooks({ silent: true });
    } catch (error) {
      appendLog(normalizeError(error, "启动翻译失败。"));
    } finally {
      setBusyAction(null);
    }
  }

  async function resumeTranslation() {
    if (isDemoBookId(currentBookId)) {
      appendLog("演示书没有可恢复的翻译任务。");
      return;
    }
    if (!currentBookId || !isMemberLike) {
      appendLog("请先加载书籍，并确认当前角色有恢复权限。");
      return;
    }
    setBusyAction("resume");
    try {
      const response = await api.resumeTranslation(currentBookId, translationPayload(selectedProviderProfile));
      appendLog(`恢复请求已发送，任务 #${jobIdOf(response) ?? "?"}。`);
      await loadBook(currentBookId, { silent: true });
      await loadBooks({ silent: true });
    } catch (error) {
      appendLog(normalizeError(error, "恢复翻译失败。"));
    } finally {
      setBusyAction(null);
    }
  }

  async function cancelTranslation() {
    if (isDemoBookId(currentBookId)) {
      appendLog("演示书没有可取消的翻译任务。");
      return;
    }
    const jobId = jobIdOf(bookDetail?.current_job);
    if (!jobId || !isMemberLike) {
      stopPolling();
      appendLog("当前没有可取消的翻译任务，已停止自动刷新。");
      return;
    }
    setBusyAction("cancel");
    try {
      await api.cancelTranslation(jobId);
      appendLog(`已取消任务 #${jobId}。`);
      if (currentBookId) {
        await loadBook(currentBookId, { silent: true });
        await loadBooks({ silent: true });
      }
    } catch (error) {
      appendLog(normalizeError(error, "取消任务失败。"));
    } finally {
      setBusyAction(null);
    }
  }

  async function updateTitle() {
    if (isDemoBookId(currentBookId)) {
      appendLog("演示书标题由 Fanbook 提供，不能编辑。");
      return;
    }
    if (!currentBookId || !bookDetail?.book || !isMemberLike) {
      appendLog("请先加载书籍，并确认当前角色有编辑权限。");
      return;
    }
    const nextValue = window.prompt("译后标题", normalizedTranslatedTitle(bookDetail.book));
    if (nextValue === null) {
      return;
    }
    try {
      const detail = await api.updateTranslatedTitle(currentBookId, nextValue.trim());
      setBookDetail(detail);
      await loadBooks({ silent: true });
      appendLog(`译后标题已更新为「${nextValue.trim() || "未设置"}」。`);
    } catch (error) {
      appendLog(normalizeError(error, "更新译后标题失败。"));
    }
  }

  async function generateArtifact(kind: ArtifactKind) {
    if (isDemoBookId(currentBookId)) {
      appendLog("演示书的导出结果已内置，无需生成。");
      return;
    }
    if (!currentBookId || !isMemberLike) {
      appendLog("当前角色不能生成导出。");
      return;
    }
    setBusyAction(`artifact-${kind}`);
    try {
      await api.generateArtifact(currentBookId, kind);
      appendLog(`${translateArtifactKind(kind)} 已生成。`);
      await loadBook(currentBookId, { silent: true });
    } catch (error) {
      appendLog(normalizeError(error, "生成导出失败。"));
    } finally {
      setBusyAction(null);
    }
  }

  async function downloadArtifact(kind: ArtifactKind) {
    if (isDemoBookId(currentBookId)) {
      appendLog(`${translateArtifactKind(kind)} 是演示资源，当前仅用于在线预览。`);
      return;
    }
    if (!currentBookId) {
      appendLog("请先加载书籍，再执行下载。");
      return;
    }
    try {
      const response = await fetch(api.artifactUrl(currentBookId, kind), {
        method: "GET",
        credentials: "same-origin",
      });
      const contentType = response.headers.get("content-type") || "";
      if (!response.ok) {
        if (contentType.includes("application/json")) {
          const payload = await response.json();
          throw new Error(payload.message || "下载失败。");
        }
        throw new Error(`下载失败，状态码 ${response.status}。`);
      }
      const blob = await response.blob();
      const filename = extractFilename(response.headers.get("content-disposition")) || defaultArtifactFilename(kind);
      downloadBlob(blob, filename);
      appendLog(`${translateArtifactKind(kind)} 下载已开始。`);
    } catch (error) {
      appendLog(normalizeError(error, "下载失败。"));
    }
  }

  async function createNote(segmentId: number) {
    if (isDemoBookId(currentBookId) || isDemoSegmentId(segmentId)) {
      appendLog("演示书笔记是只读示例。上传自己的书后可以创建私人笔记。");
      return;
    }
    if (!isMemberLike) {
      appendLog("当前角色不能创建笔记。");
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
      await api.createNote(segmentId, trimmed);
      await loadSegmentNotes(segmentId);
      appendLog(`已为段落 #${segmentId} 创建笔记。`);
      if (currentBookId && selectedReaderChapterId) {
        await loadReaderSegments(currentBookId, selectedReaderChapterId, readerMode, true);
      }
    } catch (error) {
      appendLog(normalizeError(error, "创建笔记失败。"));
    }
  }

  async function downloadNotesExport() {
    if (isDemoBookId(currentBookId)) {
      appendLog("演示书笔记仅用于在线预览。上传自己的书后可以导出私人笔记。");
      return;
    }
    if (!currentBookId) {
      appendLog("请先加载书籍，再导出笔记。");
      return;
    }
    try {
      const response = await fetch(api.notesExportUrl(currentBookId), {
        method: "GET",
        credentials: "same-origin",
      });
      if (!response.ok) {
        throw new Error(`导出失败，状态码 ${response.status}。`);
      }
      downloadBlob(await response.blob(), `book-${currentBookId}-notes.md`);
      appendLog("笔记 Markdown 导出已开始。");
    } catch (error) {
      appendLog(normalizeError(error, "导出笔记失败。"));
    }
  }

  async function loadAdminUsers() {
    try {
      const response = await api.listUsers();
      setAdminUsers(response.users || []);
    } catch (error) {
      appendLog(normalizeError(error, "加载用户列表失败。"));
    }
  }

  async function createAdminUser(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusyAction("create-user");
    try {
      await api.createUser({
        username: newUser.username.trim(),
        password: newUser.password,
        email: newUser.email.trim() || undefined,
        roles: [newUser.role],
      });
      setNewUser({ username: "", password: "", email: "", role: "MEMBER" });
      await loadAdminUsers();
      appendLog(`已创建用户 ${newUser.username.trim()}。`);
    } catch (error) {
      appendLog(normalizeError(error, "创建用户失败。"));
    } finally {
      setBusyAction(null);
    }
  }

  async function updateRoles(userId: number, roles: Role[]) {
    try {
      await api.updateUserRoles(userId, roles);
      await loadAdminUsers();
      appendLog(`用户 #${userId} 的角色已更新。`);
    } catch (error) {
      appendLog(normalizeError(error, "更新角色失败。"));
    }
  }

  function startPolling() {
    if (!currentBookId || pollTimer.current !== null) {
      setPolling(Boolean(currentBookId));
      return;
    }
    setPolling(true);
    pollTimer.current = window.setInterval(() => {
      if (currentBookId) {
        void refreshBookForPolling(currentBookId);
      }
    }, POLL_INTERVAL_MS);
  }

  function stopPolling() {
    if (pollTimer.current !== null) {
      window.clearInterval(pollTimer.current);
      pollTimer.current = null;
    }
    setPolling(false);
  }

  async function refreshBookForPolling(bookId: number) {
    try {
      const detail = await api.getBook(bookId);
      setBookDetail(detail);
      await loadBooks({ silent: true });
    } catch (error) {
      appendLog(normalizeError(error, "刷新任务状态失败。"));
    }
  }

  function appendLog(message: string) {
    const timestamp = new Date().toLocaleTimeString("zh-CN", {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
    setActivity((current) => [{ time: timestamp, message }, ...current].slice(0, 20));
  }

  function navigateTo(nextRoute: Route) {
    window.location.hash = `#/${routeToHash(nextRoute)}`;
    setRoute(nextRoute);
  }

  if (!authChecked) {
    return (
      <div className="auth-shell">
        <div className="auth-panel">
          <div className="auth-brand-lockup">
            <span className="brand-mark" aria-hidden="true"><BookOpen size={22} /></span>
            <div><strong>Fanbook</strong><p>正在检查会话...</p></div>
          </div>
        </div>
      </div>
    );
  }

  if (!currentUser) {
    return (
      <div className="auth-shell">
        <form className="auth-panel" onSubmit={login}>
          <div className="brand auth-brand">
            <span className="brand-mark" aria-hidden="true"><BookOpen size={22} /></span>
            <span>
              <strong>Fanbook</strong>
              <small>AI book translation reader</small>
            </span>
          </div>
          <label className="field">
            <span>用户名</span>
            <input value={loginUsername} onChange={(event) => setLoginUsername(event.target.value)} autoComplete="username" required />
          </label>
          <label className="field">
            <span>密码</span>
            <input value={loginPassword} onChange={(event) => setLoginPassword(event.target.value)} type="password" autoComplete="current-password" required />
          </label>
          <button className="button button-primary full" type="submit" disabled={busyAction === "login"}>
            {busyAction === "login" ? "登录中..." : "登录"}
          </button>
          <p className="profile-summary">登录后进入我的书架，阅读演示书或翻译自己的 EPUB。</p>
          <ActivityLog activity={activity} />
        </form>
      </div>
    );
  }

  const currentBook = bookDetail?.book || null;
  const currentJob = bookDetail?.current_job || null;
  const chapters = bookDetail?.chapters || [];
  const artifacts = bookDetail?.artifacts || [];
  const selectedSegment = readerSegments.find((segment) => segmentIdOf(segment) === selectedReaderSegmentId) || null;

  return (
    <div className="app-shell">
      <aside className="app-sidebar" aria-label="Fanbook 工作区">
        <a className="brand" href="#/library" onClick={(event) => { event.preventDefault(); navigateTo("library"); }}>
          <span className="brand-mark" aria-hidden="true"><BookOpen size={22} /></span>
          <span>
            <strong>Fanbook</strong>
            <small>Reader App</small>
          </span>
        </a>
        <div className="sidebar-intro">
          <span>Reader mode</span>
          <strong>翻译自己的书，然后双语阅读</strong>
        </div>
        <div className="sidebar-nav-groups">
          <nav className="page-nav" aria-label="读者导航">
            <NavLink route="library" activeRoute={route} label="我的书架" icon={<LibraryBig size={18} />} onNavigate={navigateTo} />
            <NavLink route="translate" activeRoute={route} label="翻译" icon={<Languages size={18} />} onNavigate={navigateTo} />
            <NavLink route="read" activeRoute={route} label="阅读" icon={<BookText size={18} />} onNavigate={navigateTo} />
            <NavLink route="settings" activeRoute={route} label="设置" icon={<Settings size={18} />} onNavigate={navigateTo} />
          </nav>
          {isAdmin ? (
            <nav className="page-nav admin-nav" aria-label="管理员导航">
              <span className="nav-group-label">管理</span>
              <NavLink route="admin-users" activeRoute={route} label="用户管理" icon={<UsersRound size={18} />} onNavigate={navigateTo} />
            </nav>
          ) : null}
        </div>
        <div className="sidebar-status">
          <div><span>API</span><strong>{API_BASE}</strong></div>
          <div><span>登录用户</span><strong>{currentUser.username}</strong></div>
          <div><span>角色</span><strong>{currentUser.roles.join(", ")}</strong></div>
          <div><span>任务轮询</span><strong>{polling ? `每 ${POLL_INTERVAL_MS / 1000} 秒` : "空闲"}</strong></div>
        </div>
      </aside>

      <section className="app-workspace">
        <header className="topbar">
          <div className="topbar-current">
            <span>当前书籍</span>
            <strong>{currentBook ? `${displayBookTitle(currentBook)} · #${currentBook.id}` : "未选择"}</strong>
          </div>
          <form className="quick-load" onSubmit={(event) => { event.preventDefault(); void loadBook(bookIdFromInput(bookIdInput)); }}>
            <label className="quick-load-field">
              <span aria-hidden="true">#</span>
              <input value={bookIdInput} onChange={(event) => setBookIdInput(event.target.value)} placeholder="书籍 ID / demo" />
            </label>
            <button className="button button-primary compact" type="submit">载入</button>
          </form>
          <div className="topbar-actions">
            <button className="icon-button" type="button" onClick={() => currentBookId ? void loadBook(currentBookId) : appendLog("当前没有已加载的书籍。")} aria-label="刷新当前书籍"><RefreshCw size={17} /></button>
            <button className="button button-secondary compact" type="button" onClick={logout}><LogOut size={15} />退出</button>
          </div>
          <div className="connection-strip">
            <strong className="status-dot-text"><span className="status-dot"></span>已连接</strong>
          </div>
        </header>

        <main className="app-main">
          {route === "library" ? (
            <HomePage
              books={books}
              counts={statusCounts}
              currentBookId={currentBookId}
              currentBook={currentBook}
              filter={activeBookFilter}
              onFilter={setActiveBookFilter}
              onLoadBook={(bookId) => void loadBook(bookId)}
              onOpenDemo={(nextRoute) => void openDemoBook(nextRoute)}
              onNavigate={navigateTo}
            />
          ) : null}

          {route === "translate" ? (
            <TranslatePage
              currentUser={currentUser}
              isMemberLike={isMemberLike}
              currentBook={currentBook}
              job={currentJob}
              chapters={chapters}
              artifacts={artifacts}
              providerProfiles={providerProfiles}
              selectedProviderProfileName={selectedProviderProfileName}
              activity={activity}
              busyAction={busyAction}
              fileInputRef={fileInputRef}
              titleInputRef={titleInputRef}
              languageInputRef={languageInputRef}
              onUpload={uploadBook}
              onTranslate={startTranslation}
              onResume={() => void resumeTranslation()}
              onCancel={() => void cancelTranslation()}
              onUpdateTitle={() => void updateTitle()}
              onProviderChange={(value) => {
                setSelectedProviderProfileName(value);
                localStorage.setItem(PROVIDER_PROFILE_STORAGE_KEY, value);
              }}
              onGenerate={(kind) => void generateArtifact(kind)}
              onDownload={(kind) => void downloadArtifact(kind)}
            />
          ) : null}

          {route === "read" ? (
            <ReaderPage
              currentBook={currentBook}
              isMemberLike={isMemberLike}
              chapters={readerChapters}
              selectedChapterId={selectedReaderChapterId}
              mode={readerMode}
              segments={readerSegments}
              selectedSegmentId={selectedReaderSegmentId}
              selectedSegment={selectedSegment}
              notes={segmentNotes}
              onNavigate={navigateTo}
              onSelectChapter={(chapterId) => {
                setSelectedReaderChapterId(chapterId);
                if (currentBookId) {
                  void loadReaderSegments(currentBookId, chapterId, readerMode, false);
                }
              }}
              onMode={(mode) => {
                setReaderMode(mode);
                if (currentBookId && selectedReaderChapterId) {
                  void loadReaderSegments(currentBookId, selectedReaderChapterId, mode, true);
                }
              }}
              onSelectSegment={(segmentId) => {
                setSelectedReaderSegmentId(segmentId);
                void loadSegmentNotes(segmentId);
              }}
              onCreateNote={(segmentId) => void createNote(segmentId)}
              onExportNotes={() => void downloadNotesExport()}
              isDemoBook={isDemoBookId(currentBookId)}
            />
          ) : null}

          {route === "settings" ? (
            <SettingsPage currentUser={currentUser} />
          ) : null}

          {route === "admin-users" && isAdmin ? (
            <AdminPage
              users={adminUsers}
              newUser={newUser}
              busyAction={busyAction}
              onNewUserChange={setNewUser}
              onCreateUser={createAdminUser}
              onUpdateRoles={(userId, roles) => void updateRoles(userId, roles)}
            />
          ) : null}
        </main>
      </section>
    </div>
  );
}

function NavLink({ route, activeRoute, label, icon, onNavigate }: { route: Route; activeRoute: Route; label: string; icon: React.ReactNode; onNavigate: (route: Route) => void }) {
  return (
    <a href={`#/${routeToHash(route)}`} className={activeRoute === route ? "active" : ""} onClick={(event) => { event.preventDefault(); onNavigate(route); }}>
      <span aria-hidden="true">{icon}</span>
      <strong>{label}</strong>
    </a>
  );
}

function HomePage(props: {
  books: BookListItem[];
  counts: StatusCounts;
  currentBookId: number | null;
  currentBook: BookDetail["book"] | null;
  filter: Filter;
  onFilter: (filter: Filter) => void;
  onLoadBook: (bookId: number) => void;
  onOpenDemo: (nextRoute?: Route) => void;
  onNavigate: (route: Route) => void;
}) {
  const filteredBooks = props.books.filter((book) => props.filter === "all" || String(book.status).toLowerCase() === props.filter);
  const hasBooks = props.books.length > 0;
  const currentBookIsDemo = isDemoBookId(props.currentBook?.id ?? props.currentBookId);
  const continueBook = props.currentBook || DEMO_BOOK_DETAIL.book;
  const continueBookLabel = currentBookIsDemo ? "演示书" : props.currentBook ? "私人书籍" : "推荐开始";
  return (
    <section className="page-view active">
      <div className="home-grid">
        <section className="home-command-panel">
          <div>
            <p className="eyebrow">My Library</p>
            <h1>我的书架</h1>
            <p className="hero-copy">先用演示书体验双语阅读，再把自己的 EPUB 翻译成想读的语言。私人书籍只出现在你的书架里。</p>
          </div>
          <div className="home-actions">
            {!hasBooks ? <button className="button button-primary" type="button" onClick={() => props.onOpenDemo("read")}><BookOpen size={17} />打开演示书</button> : null}
            <button className={hasBooks ? "button button-primary" : "button button-secondary"} type="button" onClick={() => props.onNavigate("translate")}><UploadCloud size={17} />上传并翻译</button>
            {hasBooks ? <button className="button button-secondary" type="button" onClick={() => props.onNavigate("read")}><BookOpen size={17} />继续阅读</button> : null}
          </div>
        </section>
        <section className="metric-grid">
          <Metric label="总书籍" value={props.counts.total} className="metric-total" />
          <Metric label="进行中" value={props.counts.running} />
          <Metric label="已完成" value={props.counts.completed} />
          <Metric label="失败" value={props.counts.failed} />
        </section>
        <section className="library-panel surface-panel">
          <div className="section-heading">
            <div><p className="eyebrow">Private Shelf</p><h2>我的书</h2><p>{hasBooks ? "选择一本书后，翻译和阅读视图会同步更新。" : "你的私人书架还没有书。演示书不会占用这里。"}</p></div>
          </div>
          <div className="library-tabs">
            {(["all", "running", "completed", "failed"] as Filter[]).map((filter) => (
              <button key={filter} className={`tab-button${props.filter === filter ? " active" : ""}`} type="button" onClick={() => props.onFilter(filter)}>
                {filterLabel(filter)} <span>{filterCount(filter, props.counts)}</span>
              </button>
            ))}
          </div>
          <div className="book-list">
            {filteredBooks.length ? filteredBooks.map((book) => (
              <BookRow key={book.id} book={book} active={props.currentBookId === book.id} onLoadBook={props.onLoadBook} />
            )) : (
              <div className="library-empty-card">
                <div className="empty-visual compact-empty-visual" aria-hidden="true"><span></span><span></span><span></span></div>
                <div>
                  <strong>先读演示书，再上传自己的 EPUB</strong>
                  <p>演示书是 Fanbook 自写样例，用来展示原文、译文、双语模式和示例笔记。你的私人书籍会在上传后显示在这里。</p>
                </div>
                <div className="empty-actions">
                  <button className="button button-primary" type="button" onClick={() => props.onOpenDemo("read")}><BookOpen size={17} />打开演示书</button>
                  <button className="button button-secondary" type="button" onClick={() => props.onNavigate("translate")}><UploadCloud size={17} />上传 EPUB</button>
                </div>
              </div>
            )}
          </div>
        </section>
        <section className="continue-panel surface-panel">
          <div className="section-heading compact-heading">
            <div><p className="eyebrow">Continue</p><h2>{hasBooks || props.currentBook ? "继续阅读" : "先体验一次"}</h2></div>
            <span className="status-pill status-accent">{continueBookLabel}</span>
          </div>
          <div className="continue-book-card">
            <div className="selected-book-cover compact-cover" style={{ background: getBookCoverStyle(continueBook) }}>
              <span>{bookCoverInitials(continueBook)}</span>
            </div>
            <div className="continue-copy">
              <strong>{displayBookTitle(continueBook)}</strong>
              <p>{currentBookIsDemo || !props.currentBook ? "打开内置演示书，先看 Fanbook 的双语阅读体验。" : "回到阅读器，继续查看章节、段落和笔记。"}</p>
              <div className="continue-actions">
                <button className="button button-primary compact" type="button" onClick={() => {
                  if (!props.currentBook || currentBookIsDemo) {
                    props.onOpenDemo();
                  }
                  props.onNavigate("read");
                }}><BookOpen size={16} />阅读</button>
                <button className="button button-secondary compact" type="button" onClick={() => props.onNavigate("translate")}><Languages size={16} />翻译</button>
              </div>
            </div>
          </div>
        </section>
        <section className="demo-book-panel surface-panel">
          <div className="section-heading compact-heading">
            <div><p className="eyebrow">Demo Book</p><h2>Fanbook 演示书</h2></div>
            <span className="status-pill status-success">内置样例</span>
          </div>
          <BookRow book={DEMO_BOOK_LIST_ITEM} active={currentBookIsDemo} onLoadBook={props.onLoadBook} variant="demo" />
          <p className="demo-book-copy">这本短篇由 Fanbook 提供，只用于体验双语阅读、阅读模式切换和示例笔记。它不是公共版权书，也不会混入你的私人书架统计。</p>
        </section>
        <aside className="selected-book-panel surface-panel">
          <div className="section-heading"><div><p className="eyebrow">Reading Desk</p><h2>当前书籍</h2><p>选中状态</p></div></div>
          {props.currentBook ? (
            <>
            <div className="selected-book-cover" style={{ background: getBookCoverStyle(props.currentBook) }}>
              <span>{bookCoverInitials(props.currentBook)}</span>
            </div>
            <dl className="metadata-list">
              <div><dt>标题</dt><dd>{displayBookTitle(props.currentBook)}</dd></div>
              <div><dt>文件</dt><dd>{props.currentBook.filename}</dd></div>
              <div><dt>语言</dt><dd>{sourceLanguageLabel(props.currentBook.source_language)} → 中文</dd></div>
              <div><dt>类型</dt><dd>{currentBookIsDemo ? "Fanbook 内置演示书" : "私人书籍"}</dd></div>
              <div><dt>状态</dt><dd><span className={`status-pill ${statusBadgeClass(props.currentBook.status)}`}>{translateStatus(props.currentBook.status)}</span></dd></div>
            </dl>
            </>
          ) : <div className="empty-state">请选择一本私人书籍，或打开演示书体验阅读。</div>}
        </aside>
      </div>
    </section>
  );
}

function BookRow({ book, active, onLoadBook, variant = "default" }: { book: BookListItem; active: boolean; onLoadBook: (bookId: number) => void; variant?: "default" | "demo" }) {
  return (
    <article className={`book-row${active ? " active" : ""}${variant === "demo" ? " demo-book-row" : ""}`} role="button" tabIndex={0} onClick={() => onLoadBook(book.id)} onKeyDown={(event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onLoadBook(book.id);
      }
    }}>
      <div className="mini-cover" style={{ background: getBookCoverStyle(book) }}>{bookCoverInitials(book)}</div>
      <div>
        <h2>{displayBookTitle(book) || "未命名书籍"}</h2>
        <p>{book.filename} · {sourceLanguageLabel(book.source_language)} · {Math.round((book.progress || 0) * 100)}%</p>
      </div>
      <time>{formatDateTime(book.updated_at || book.created_at)}</time>
      <span className={`book-status ${bookStatusClassName(book.status)}`}>{variant === "demo" ? "演示书" : translateStatus(book.status)}</span>
    </article>
  );
}

function TranslatePage(props: {
  currentUser: CurrentUser;
  isMemberLike: boolean;
  currentBook: BookDetail["book"] | null;
  job: TranslationJob | null;
  chapters: ChapterSummary[];
  artifacts: ExportArtifact[];
  providerProfiles: ProviderProfile[];
  selectedProviderProfileName: string | null;
  activity: ActivityEntry[];
  busyAction: string | null;
  fileInputRef: React.RefObject<HTMLInputElement | null>;
  titleInputRef: React.RefObject<HTMLInputElement | null>;
  languageInputRef: React.RefObject<HTMLInputElement | null>;
  onUpload: (event: React.FormEvent<HTMLFormElement>) => void;
  onTranslate: (event: React.FormEvent<HTMLFormElement>) => void;
  onResume: () => void;
  onCancel: () => void;
  onUpdateTitle: () => void;
  onProviderChange: (value: string) => void;
  onGenerate: (kind: ArtifactKind) => void;
  onDownload: (kind: ArtifactKind) => void;
}) {
  const totals = totalsFromJob(props.job, totalsFromChapters(props.chapters));
  const percentage = clamp((props.job?.progress ?? (totals.total ? totals.translated / totals.total : 0)) * 100);
  const activeJob = ["pending", "queued", "running"].includes(String(props.job?.status || "").toLowerCase());
  const canResume = Boolean(props.currentBook && ["failed", "canceled"].includes(String(props.job?.status || "").toLowerCase()));
  const canRun = props.isMemberLike && Boolean(props.currentBook) && Boolean(props.providerProfiles.length) && !activeJob;
  return (
    <section className="page-view active">
      <div className="translate-grid">
        <aside className="translate-tools">
          <section className="tool-panel">
            <div className="section-heading compact-heading"><div><p className="eyebrow">Import</p><h2>上传 EPUB</h2></div></div>
            <form className="upload-form" onSubmit={props.onUpload}>
              <label className="upload-dropzone">
                <span aria-hidden="true"><UploadCloud size={24} /></span>
                <strong>上传 EPUB</strong>
                <input ref={props.fileInputRef} type="file" accept=".epub" required disabled={!props.isMemberLike} />
              </label>
              <label className="field"><span>标题覆盖</span><input ref={props.titleInputRef} type="text" placeholder="可选" disabled={!props.isMemberLike} /></label>
              <label className="field"><span>源语言</span><input ref={props.languageInputRef} type="text" defaultValue="en" disabled={!props.isMemberLike} /></label>
              <button className="button button-secondary full" type="submit" disabled={!props.isMemberLike || props.busyAction === "upload"}>
                {props.busyAction === "upload" ? "上传中..." : "上传并解析"}
              </button>
            </form>
          </section>
          <section className="tool-panel">
            <div className="section-heading compact-heading"><div><p className="eyebrow">Run</p><h2>翻译任务</h2></div></div>
            <form className="translation-form" onSubmit={props.onTranslate}>
              <label className="field">
                <span>配置档</span>
                <select value={props.selectedProviderProfileName || ""} onChange={(event) => props.onProviderChange(event.target.value)}>
                  {props.providerProfiles.length ? props.providerProfiles.map((profile) => (
                    <option key={profile.profile_name} value={profile.profile_name}>{profile.profile_name}{profile.is_default ? "（默认）" : ""}</option>
                  )) : <option value="">未找到可用配置</option>}
                </select>
              </label>
              <p className="profile-summary">{providerSummary(props.providerProfiles, props.selectedProviderProfileName)}</p>
              <button className="button button-primary full" type="submit" disabled={!canRun || props.busyAction === "translate"}><Play size={16} />开始翻译</button>
              <button className="button button-secondary full" type="button" onClick={props.onResume} disabled={!props.isMemberLike || !canResume}><RotateCcw size={16} />恢复任务</button>
              <button className="button button-danger full" type="button" onClick={props.onCancel} disabled={!props.isMemberLike || !activeJob}><XCircle size={16} />取消任务</button>
            </form>
          </section>
        </aside>
        <section className={`translate-workspace${props.currentBook ? "" : " is-empty"}`}>
          {!props.currentBook ? (
            <div className="page-empty-state">
              <div className="empty-visual" aria-hidden="true"><span></span><span></span><span></span></div>
              <h2>开始翻译你的第一本书</h2>
              <p>上传 EPUB 或载入最近书籍后，翻译进度、章节状态和导出结果会集中显示在这里。</p>
            </div>
          ) : (
            <div className="translate-content">
              <section className="book-hero surface-panel">
                <div className="book-cover" style={{ background: getBookCoverStyle(props.currentBook) }}><span>{bookCoverInitials(props.currentBook)}</span></div>
                <div className="book-identity">
                  <p className="eyebrow">Book</p>
                  <dl className="metadata-list">
                    <div><dt>原标题</dt><dd>{props.currentBook.title}</dd></div>
                    <div><dt>译后标题</dt><dd>{renderTranslatedTitle(props.currentBook)} {props.isMemberLike ? <button className="text-button inline-action" type="button" onClick={props.onUpdateTitle}>编辑</button> : null}</dd></div>
                    <div><dt>书籍 ID</dt><dd>{props.currentBook.id}</dd></div>
                    <div><dt>文件名</dt><dd>{props.currentBook.filename}</dd></div>
                    <div><dt>源语言</dt><dd>{sourceLanguageLabel(props.currentBook.source_language)}</dd></div>
                  </dl>
                </div>
              </section>
              <section className="summary-panel surface-panel">
                <div className="section-heading">
                  <div><p className="eyebrow">Progress</p><h2><Gauge size={18} />翻译进度</h2></div>
                  <span className={`status-pill ${statusBadgeClass(props.job?.status || "idle")}`}>{translateStatus(props.job?.status || "idle")}</span>
                </div>
                <div className="summary-body">
                  <div className="progress-ring" style={{ "--progress": `${percentage}%` } as React.CSSProperties}>
                    <span>{Math.round(percentage)}%</span><small>整体进度</small>
                  </div>
                  <div className="summary-stats">
                    <Stat label="总段落" value={totals.total} />
                    <Stat label="已翻译" value={totals.translated} className="accent-text" />
                    <Stat label="失败" value={totals.failed} className="danger-text" />
                    <Stat label="剩余" value={Math.max(0, totals.total - totals.translated - totals.failed)} />
                  </div>
                </div>
                <div className="progress-inline"><div className="progress-bar" style={{ width: `${percentage}%` }}></div></div>
                <p className="estimate-text">{props.job ? `预计剩余时间：${estimateRemainingTime(props.job, totals, percentage)}` : "当前没有活动任务"}</p>
              </section>
              <section className="exports-panel surface-panel">
                <div className="section-heading compact-heading"><div><p className="eyebrow">Output</p><h2><Archive size={18} />导出</h2></div></div>
                <div className="export-list">
                  {(["zh", "bilingual", "consistency_report"] as ArtifactKind[]).map((kind) => (
                    <ExportCard key={kind} kind={kind} artifact={findArtifact(props.artifacts, kind)} />
                  ))}
                </div>
                <div className="export-actions">
                  {(["zh", "bilingual", "consistency_report"] as ArtifactKind[]).map((kind) => {
                    const ready = Boolean(findReadyArtifact(props.artifacts, kind));
                    return (
                      <div key={kind} className="export-action-row">
                        {props.isMemberLike ? <button className="button button-secondary full" type="button" onClick={() => props.onGenerate(kind)} disabled={props.busyAction === `artifact-${kind}`}>生成{translateArtifactKind(kind)}</button> : null}
                        <button className="button button-secondary full" type="button" onClick={() => props.onDownload(kind)} disabled={!ready}><Download size={16} />下载{translateArtifactKind(kind)}</button>
                      </div>
                    );
                  })}
                </div>
              </section>
              <section className="chapters-panel surface-panel">
                <div className="section-heading"><div><p className="eyebrow">Chapters</p><h2><ScrollText size={18} />章节状态</h2></div></div>
                <ChapterTable chapters={props.chapters} />
              </section>
              <section className="log-workspace-panel surface-panel">
                <div className="section-heading compact-heading"><div><p className="eyebrow">Activity</p><h2><Activity size={18} />活动日志</h2></div></div>
                <ActivityLog activity={props.activity} />
              </section>
            </div>
          )}
        </section>
      </div>
    </section>
  );
}

function ReaderPage(props: {
  currentBook: BookDetail["book"] | null;
  isMemberLike: boolean;
  isDemoBook: boolean;
  chapters: ChapterSummary[];
  selectedChapterId: number | null;
  mode: ReaderMode;
  segments: ReaderSegment[];
  selectedSegmentId: number | null;
  selectedSegment: ReaderSegment | null;
  notes: SegmentNote[];
  onNavigate: (route: Route) => void;
  onSelectChapter: (chapterId: number) => void;
  onMode: (mode: ReaderMode) => void;
  onSelectSegment: (segmentId: number) => void;
  onCreateNote: (segmentId: number) => void;
  onExportNotes: () => void;
}) {
  if (!props.currentBook) {
    return (
      <section className="page-view active">
        <div className="page-empty-state">
          <div className="empty-visual reader-empty-visual" aria-hidden="true"><span></span><span></span><span></span></div>
          <h2>未选择阅读书籍</h2>
          <p>从书库选择一本书后，阅读器会显示章节、段落和笔记。</p>
          <button className="button button-primary" type="button" onClick={() => props.onNavigate("library")}><LibraryBig size={17} />回到我的书架</button>
        </div>
      </section>
    );
  }
  return (
    <section className="page-view active">
      <div className="reader-layout">
        <aside className="reader-sidebar surface-panel">
          <div className="section-heading compact-heading"><div><p className="eyebrow">Reader Lab</p><h2>阅读控制</h2></div></div>
          <div className="reader-bookplate">
            <span style={{ background: getBookCoverStyle(props.currentBook) }} aria-hidden="true">{bookCoverInitials(props.currentBook)}</span>
            <strong>{displayBookTitle(props.currentBook)}</strong>
          </div>
          <label className="field reader-field">
            <span>章节</span>
            <select value={props.selectedChapterId || ""} onChange={(event) => props.onSelectChapter(Number(event.target.value))}>
              {props.chapters.map((chapter) => <option key={chapterIdOf(chapter)} value={chapterIdOf(chapter) || ""}>#{chapter.chapterOrder || chapter.order || chapterIdOf(chapter)} · {chapter.title}</option>)}
            </select>
          </label>
          <label className="field reader-field">
            <span>阅读模式</span>
            <select value={props.mode} onChange={(event) => props.onMode(event.target.value as ReaderMode)}>
              <option value="bilingual">双语</option>
              <option value="original">原文</option>
              <option value="translated">译文</option>
            </select>
          </label>
          <button className="button button-secondary full" type="button" onClick={props.onExportNotes} disabled={props.isDemoBook}><Download size={16} />{props.isDemoBook ? "演示笔记只读" : "导出笔记"}</button>
        </aside>
        <section className="reader-panel surface-panel">
          <div className="section-heading"><div><p className="eyebrow">Bilingual Review</p><h2><BookMarked size={18} />在线阅读</h2></div></div>
          <div className="reader-segments">
            {props.segments.length ? props.segments.map((segment) => {
              const segmentId = segmentIdOf(segment);
              return (
                <article key={segmentId} className={`reader-segment${props.mode === "bilingual" ? " bilingual" : " single"}${props.selectedSegmentId === segmentId ? " active" : ""}`}>
                  <div className="reader-segment-main" role="button" tabIndex={0} onClick={() => segmentId && props.onSelectSegment(segmentId)}>
                    <header className="reader-segment-head">
                      <div className="reader-segment-meta">
                        <strong>段落 #{segment.order || segmentId}</strong>
                        <span>{segment.type || "segment"}</span>
                        <span className={`status-pill ${statusBadgeClass(segment.translationStatus || segment.translation_status)}`}>{translateStatus(segment.translationStatus || segment.translation_status)}</span>
                      </div>
                    </header>
                    <div className="reader-segment-body">
                      {props.mode !== "translated" ? <ReaderColumn label="原文" text={segment.sourceText || segment.source_text || "暂无原文"} /> : null}
                      {props.mode !== "original" ? <ReaderColumn label="译文" text={segment.translatedText || segment.translated_text || "暂无译文"} /> : null}
                    </div>
                  </div>
                  {props.isMemberLike && segmentId && !props.isDemoBook ? <button className="text-button reader-note-button" type="button" onClick={() => props.onCreateNote(segmentId)}><NotebookPen size={15} />{Number(segment.noteCount ?? segment.note_count ?? 0) > 0 ? `笔记 ${segment.noteCount ?? segment.note_count}` : "添加笔记"}</button> : null}
                </article>
              );
            }) : <div className="empty-state">当前章节没有可显示的段落。</div>}
          </div>
        </section>
        <aside className="segment-notes-panel surface-panel">
          {!props.selectedSegment ? <div className="segment-notes-empty empty-state">选择一个段落后，笔记会显示在这里。</div> : (
            <>
              <div className="segment-notes-header">
                <div><strong>段落 #{props.selectedSegment.order || segmentIdOf(props.selectedSegment)}</strong><p>{props.selectedSegment.sourceText || props.selectedSegment.source_text || "暂无原文"}</p></div>
                {props.isMemberLike && segmentIdOf(props.selectedSegment) && !props.isDemoBook ? <button className="text-button" type="button" onClick={() => props.onCreateNote(segmentIdOf(props.selectedSegment)!)}><NotebookPen size={15} />新建笔记</button> : props.isDemoBook ? <span className="status-pill status-neutral">演示笔记只读</span> : null}
              </div>
              <div className="segment-notes-list">
                {props.notes.length ? props.notes.map((note) => (
                  <article key={note.noteId || note.id} className="segment-note-card">
                    <header><strong>{note.createdBy || note.created_by || "-"}</strong><time>{formatDateTime(note.createdAt || note.created_at)}</time></header>
                    <p>{note.content || note.note_content || ""}</p>
                  </article>
                )) : <div className="empty-state">这个段落还没有笔记。</div>}
              </div>
            </>
          )}
        </aside>
      </div>
    </section>
  );
}

function SettingsPage({ currentUser }: { currentUser: CurrentUser }) {
  return (
    <section className="page-view active">
      <div className="settings-layout">
        <section className="surface-panel settings-hero-panel">
          <div>
            <p className="eyebrow">Settings</p>
            <h1>个人 AI 设置</h1>
            <p className="hero-copy">这里将保存你的 Provider、模型和 API Key，用于翻译你自己的书。密钥保存能力会在后端加密存储完成后接入。</p>
          </div>
          <div className="settings-user-chip">
            <span aria-hidden="true"><UserRoundPlus size={18} /></span>
            <div><strong>{currentUser.username}</strong><small>{currentUser.roles.join(", ")}</small></div>
          </div>
        </section>

        <section className="surface-panel settings-panel">
          <div className="section-heading">
            <div><p className="eyebrow">AI Profiles</p><h2><KeyRound size={18} />我的模型配置</h2><p>后续可保存多个配置，并设置一个默认配置。翻译单本书时可以临时切换。</p></div>
          </div>
          <div className="settings-profile-list">
            <article className="settings-profile-card is-default">
              <div>
                <strong>默认配置</strong>
                <p>尚未连接后端个人密钥存储。当前翻译仍沿用平台 Provider 配置。</p>
              </div>
              <span className="status-pill status-neutral">待配置</span>
            </article>
          </div>
        </section>

        <section className="surface-panel settings-panel">
          <div className="section-heading">
            <div><p className="eyebrow">Provider</p><h2><ServerCog size={18} />支持的 Provider</h2><p>产品目标是支持 OpenAI、Anthropic、Gemini、DeepSeek 等预设 Provider。</p></div>
          </div>
          <div className="provider-option-grid" aria-label="支持的 AI Provider">
            {["OpenAI", "Anthropic", "Gemini", "DeepSeek"].map((provider) => (
              <article key={provider} className="provider-option-card">
                <strong>{provider}</strong>
                <span>计划支持</span>
              </article>
            ))}
          </div>
        </section>

        <section className="surface-panel settings-panel settings-security-panel">
          <div className="section-heading compact-heading">
            <div><p className="eyebrow">Security</p><h2><Shield size={18} />密钥安全边界</h2></div>
          </div>
          <ul className="settings-check-list">
            <li>API Key 不应长期明文保存在浏览器本地存储。</li>
            <li>保存后前端只应显示 masked key。</li>
            <li>后端需要按用户隔离并加密保存密钥。</li>
          </ul>
        </section>
      </div>
    </section>
  );
}

function AdminPage(props: {
  users: AdminUser[];
  newUser: { username: string; password: string; email: string; role: Role };
  busyAction: string | null;
  onNewUserChange: (value: { username: string; password: string; email: string; role: Role }) => void;
  onCreateUser: (event: React.FormEvent<HTMLFormElement>) => void;
  onUpdateRoles: (userId: number, roles: Role[]) => void;
}) {
  return (
    <section className="page-view active">
      <div className="admin-grid">
        <section className="surface-panel admin-panel">
          <div className="section-heading"><div><p className="eyebrow">Admin</p><h2><Shield size={18} />用户管理</h2></div></div>
          <div className="chapter-table">
            <table>
              <thead><tr><th>用户名</th><th>邮箱</th><th>角色</th><th>状态</th><th>操作</th></tr></thead>
              <tbody>
                {props.users.map((user) => (
                  <tr key={user.id}>
                    <td>{user.username}</td>
                    <td>{user.email || "-"}</td>
                    <td>{user.roles.join(", ")}</td>
                    <td>{user.enabled ? "启用" : "停用"}</td>
                    <td>
                      <select value={user.roles[0] || "VIEWER"} onChange={(event) => props.onUpdateRoles(user.id, [event.target.value as Role])}>
                        <option value="ADMIN">ADMIN</option>
                        <option value="MEMBER">MEMBER</option>
                        <option value="VIEWER">VIEWER</option>
                      </select>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
        <form className="surface-panel admin-panel admin-form" onSubmit={props.onCreateUser}>
          <div className="section-heading compact-heading"><div><p className="eyebrow">Create</p><h2><UserRoundPlus size={18} />新建用户</h2></div></div>
          <label className="field"><span>用户名</span><input value={props.newUser.username} onChange={(event) => props.onNewUserChange({ ...props.newUser, username: event.target.value })} required /></label>
          <label className="field"><span>初始密码</span><input type="password" value={props.newUser.password} onChange={(event) => props.onNewUserChange({ ...props.newUser, password: event.target.value })} required /></label>
          <label className="field"><span>邮箱</span><input type="email" value={props.newUser.email} onChange={(event) => props.onNewUserChange({ ...props.newUser, email: event.target.value })} /></label>
          <label className="field"><span>角色</span><select value={props.newUser.role} onChange={(event) => props.onNewUserChange({ ...props.newUser, role: event.target.value as Role })}><option value="MEMBER">MEMBER</option><option value="VIEWER">VIEWER</option><option value="ADMIN">ADMIN</option></select></label>
          <button className="button button-primary full" type="submit" disabled={props.busyAction === "create-user"}>创建用户</button>
        </form>
      </div>
    </section>
  );
}

function Metric({ label, value, className = "" }: { label: string; value: number; className?: string }) {
  return <article className={`metric-card ${className}`}><span>{label}</span><strong>{formatNumber(value)}</strong></article>;
}

function Stat({ label, value, className = "" }: { label: string; value: number; className?: string }) {
  return <div><span>{label}</span><strong className={className}>{formatNumber(value)}</strong></div>;
}

function ExportCard({ kind, artifact }: { kind: ArtifactKind; artifact?: ExportArtifact }) {
  const status = translateStatus(artifact?.status || "pending");
  const size = artifact?.size ?? artifact?.sizeBytes ?? null;
  const Icon = kind === "consistency_report" ? CheckCircle2 : kind === "bilingual" ? Languages : FileText;
  return <article><strong><Icon size={16} />{translateArtifactKind(kind)}</strong><span>{status} · {size ? formatBytes(size) : "等待生成"}</span></article>;
}

function ChapterTable({ chapters }: { chapters: ChapterSummary[] }) {
  if (!chapters.length) {
    return <div className="empty-state">载入书籍后，这里会显示章节进度。</div>;
  }
  return (
    <div className="chapter-table">
      <table>
        <thead><tr><th>章节</th><th>段落数</th><th>已翻译</th><th>失败</th><th>进度</th></tr></thead>
        <tbody>
          {chapters.map((chapter) => {
            const total = totalOf(chapter);
            const translated = translatedOf(chapter);
            const failed = failedOf(chapter);
            const progress = total ? (translated / total) * 100 : 0;
            return (
              <tr key={chapterIdOf(chapter) || chapter.title}>
                <td>{chapter.order || chapter.chapterOrder || chapterIdOf(chapter)}. {chapter.title}</td>
                <td>{formatNumber(total)}</td>
                <td>{formatNumber(translated)}</td>
                <td>{formatNumber(failed)}</td>
                <td><span className="row-progress"><i style={{ width: `${clamp(progress)}%` }}></i></span><strong>{Math.round(progress)}%</strong></td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function ReaderColumn({ label, text }: { label: string; text: string }) {
  return <div className="reader-segment-column"><span className="reader-segment-kicker">{label}</span><p>{text}</p></div>;
}

function ActivityLog({ activity }: { activity: ActivityEntry[] }) {
  if (!activity.length) {
    return <div className="message-log"><div className="empty-state">暂无活动记录。</div></div>;
  }
  return (
    <div className="message-log" aria-live="polite">
      {activity.slice(0, 10).map((entry, index) => (
        <article key={`${entry.time}-${index}`} className="log-entry">
          <span className="log-time">{entry.time}</span>
          <p className="log-message">{entry.message}</p>
        </article>
      ))}
    </div>
  );
}

function normalizeRoute(hash: string): Route {
  const route = hash.replace(/^#\/?/, "").trim().toLowerCase();
  if (route === "home" || route === "") {
    return "library";
  }
  if (route === "admin") {
    return "admin-users";
  }
  if (["library", "translate", "read", "settings", "admin-users"].includes(route)) {
    return route as Route;
  }
  return "library";
}

function routeToHash(route: Route): string {
  return route;
}

function updateBookIdSearch(bookId: number) {
  const url = new URL(window.location.href);
  url.searchParams.set("bookId", isDemoBookId(bookId) ? DEMO_BOOK_STORAGE_VALUE : String(bookId));
  window.history.replaceState({}, "", url);
}

function bookIdFromStorage(value: string | null) {
  return bookIdFromInput(value || "");
}

function bookIdFromInput(value: string) {
  const normalized = value.trim().toLowerCase();
  if (normalized === DEMO_BOOK_STORAGE_VALUE || normalized === String(DEMO_BOOK_ID)) {
    return DEMO_BOOK_ID;
  }
  return Number(value);
}

function isDemoBookId(bookId: number | null | undefined) {
  return bookId === DEMO_BOOK_ID;
}

function isDemoSegmentId(segmentId: number | null | undefined) {
  return Boolean(segmentId && segmentId < 0);
}

function cloneDemoBookDetail(): BookDetail {
  return {
    book: { ...DEMO_BOOK_DETAIL.book },
    current_job: DEMO_BOOK_DETAIL.current_job ? { ...DEMO_BOOK_DETAIL.current_job } : null,
    chapters: DEMO_BOOK_DETAIL.chapters.map((chapter) => ({ ...chapter })),
    artifacts: DEMO_BOOK_DETAIL.artifacts.map((artifact) => ({ ...artifact })),
  };
}

function cloneDemoReaderSegments(chapterId: number): ReaderSegment[] {
  return (DEMO_READER_SEGMENTS[chapterId] || []).map((segment) => ({ ...segment }));
}

function cloneDemoSegmentNotes(segmentId: number): SegmentNote[] {
  return (DEMO_SEGMENT_NOTES[segmentId] || []).map((note) => ({ ...note }));
}

function hasRole(user: CurrentUser | null, role: Role) {
  return Boolean(user?.roles.includes(role));
}

function hasAnyRole(user: CurrentUser | null, roles: Role[]) {
  return Boolean(user?.roles.some((role) => roles.includes(role)));
}

function pickProvider(profiles: ProviderProfile[], name: string | null) {
  return profiles.find((profile) => profile.profile_name === name) || profiles.find((profile) => profile.is_default) || profiles[0] || null;
}

function providerSummary(profiles: ProviderProfile[], selectedName: string | null) {
  const profile = pickProvider(profiles, selectedName);
  if (!profile) {
    return "当前没有可用的翻译配置档。";
  }
  return `当前使用 ${profile.profile_name}，provider 为 ${profile.provider_name}，模型为 ${profile.default_model_name}，状态 ${profile.configured ? "已配置" : "未配置"}。`;
}

function translationPayload(profile: ProviderProfile | null) {
  return profile ? { providerName: profile.provider_name, modelName: profile.default_model_name } : {};
}

function totalsFromChapters(chapters: ChapterSummary[]) {
  return chapters.reduce((totals, chapter) => ({
    total: totals.total + totalOf(chapter),
    translated: totals.translated + translatedOf(chapter),
    failed: totals.failed + failedOf(chapter),
  }), { total: 0, translated: 0, failed: 0 });
}

function totalsFromJob(job: TranslationJob | null, fallback: { total: number; translated: number; failed: number }) {
  return {
    total: Number(job?.total_segments ?? job?.totalSegments ?? fallback.total) || 0,
    translated: Number(job?.translated_segments ?? job?.translatedSegments ?? fallback.translated) || 0,
    failed: Number(job?.failed_segments ?? job?.failedSegments ?? fallback.failed) || 0,
  };
}

function totalOf(chapter: ChapterSummary) {
  return Number(chapter.total_segments ?? chapter.totalSegments ?? 0) || 0;
}

function translatedOf(chapter: ChapterSummary) {
  return Number(chapter.translated_segments ?? chapter.translatedSegments ?? 0) || 0;
}

function failedOf(chapter: ChapterSummary) {
  return Number(chapter.failed_segments ?? chapter.failedSegments ?? 0) || 0;
}

function chapterIdOf(chapter: ChapterSummary) {
  return Number(chapter.chapterId ?? chapter.id ?? 0) || null;
}

function segmentIdOf(segment: ReaderSegment | null) {
  return Number(segment?.segmentId ?? segment?.id ?? 0) || null;
}

function pickReaderChapterId(chapters: ChapterSummary[], preferred: number | null) {
  if (preferred && chapters.some((chapter) => chapterIdOf(chapter) === preferred)) {
    return preferred;
  }
  return chapterIdOf(chapters[0]) || null;
}

function pickReaderSegmentId(segments: ReaderSegment[], preferred: number | null) {
  if (preferred && segments.some((segment) => segmentIdOf(segment) === preferred)) {
    return preferred;
  }
  return segmentIdOf(segments[0]) || null;
}

function jobIdOf(job: TranslationJob | null | undefined) {
  return Number(job?.job_id ?? job?.jobId ?? 0) || null;
}

function findArtifact(artifacts: ExportArtifact[], kind: ArtifactKind) {
  return artifacts.find((artifact) => artifact.kind === kind);
}

function findReadyArtifact(artifacts: ExportArtifact[], kind: ArtifactKind) {
  return artifacts.find((artifact) => artifact.kind === kind && String(artifact.status).toLowerCase() === "ready");
}

function defaultArtifactFilename(kind: ArtifactKind) {
  if (kind === "zh") {
    return "zh.epub";
  }
  if (kind === "bilingual") {
    return "bilingual.epub";
  }
  return "consistency.json";
}

function downloadBlob(blob: Blob, filename: string) {
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.append(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

function estimateRemainingTime(job: TranslationJob, totals: { total: number; translated: number; failed: number }, percentage: number) {
  const explicitSeconds = Number(job.estimated_remaining_seconds);
  if (Number.isFinite(explicitSeconds) && explicitSeconds > 0) {
    return formatDuration(explicitSeconds);
  }
  if (!totals.total || percentage <= 0 || percentage >= 100) {
    return percentage >= 100 ? "0 分钟" : "计算中";
  }
  const remaining = Math.max(0, totals.total - totals.translated - totals.failed);
  return remaining ? formatDuration(Math.round(remaining * 2.2)) : "0 分钟";
}

function filterLabel(filter: Filter) {
  return filter === "all" ? "全部" : filter === "running" ? "进行中" : filter === "completed" ? "已完成" : "失败";
}

function filterCount(filter: Filter, counts: StatusCounts) {
  return filter === "all" ? counts.total : counts[filter];
}

function bookStatusClassName(status: string) {
  switch (String(status || "").toLowerCase()) {
    case "completed":
      return "done";
    case "failed":
      return "failed";
    default:
      return "running";
  }
}

function clamp(value: number) {
  return Math.max(0, Math.min(100, Number.isFinite(value) ? value : 0));
}

const rootElement = document.getElementById("root");
if (!rootElement) {
  throw new Error("Missing #root element.");
}

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>
);
