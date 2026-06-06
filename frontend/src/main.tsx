import { StrictMode, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
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

type Route = "home" | "translate" | "read" | "admin";
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
    const remembered = localStorage.getItem(STORAGE_KEY);
    if (remembered) {
      setBookIdInput(remembered);
      void loadBook(Number(remembered), { silent: true });
    } else {
      appendLog("系统已就绪，等待上传 EPUB 或加载现有书籍 ID。");
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
    if (isAdmin && route === "admin") {
      void loadAdminUsers();
    }
  }, [isAdmin, route]);

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

  async function loadReader(bookId: number, options: { preserveSelection?: boolean } = {}) {
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
    window.location.hash = `#/${nextRoute}`;
    setRoute(nextRoute);
  }

  if (!authChecked) {
    return <div className="auth-shell"><div className="auth-panel"><strong>Fanbook</strong><p>正在检查会话...</p></div></div>;
  }

  if (!currentUser) {
    return (
      <div className="auth-shell">
        <form className="auth-panel" onSubmit={login}>
          <div className="brand auth-brand">
            <span className="brand-mark" aria-hidden="true">F</span>
            <span>
              <strong>Fanbook</strong>
              <small>Private team workspace</small>
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
          <p className="profile-summary">首次管理员通过部署环境变量初始化；本页面不提供公开 setup。</p>
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
        <a className="brand" href="#/home" onClick={(event) => { event.preventDefault(); navigateTo("home"); }}>
          <span className="brand-mark" aria-hidden="true">F</span>
          <span>
            <strong>Fanbook</strong>
            <small>EPUB Translation</small>
          </span>
        </a>
        <nav className="page-nav" aria-label="主导航">
          <NavLink route="home" activeRoute={route} label="书库" icon="⌂" onNavigate={navigateTo} />
          <NavLink route="translate" activeRoute={route} label="翻译" icon="⇄" onNavigate={navigateTo} />
          <NavLink route="read" activeRoute={route} label="阅读" icon="☰" onNavigate={navigateTo} />
          {isAdmin ? <NavLink route="admin" activeRoute={route} label="用户" icon="◎" onNavigate={navigateTo} /> : null}
        </nav>
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
          <form className="quick-load" onSubmit={(event) => { event.preventDefault(); void loadBook(Number(bookIdInput)); }}>
            <label className="quick-load-field">
              <span aria-hidden="true">#</span>
              <input value={bookIdInput} onChange={(event) => setBookIdInput(event.target.value)} placeholder="书籍 ID" />
            </label>
            <button className="button button-primary compact" type="submit">载入</button>
          </form>
          <div className="topbar-actions">
            <button className="icon-button" type="button" onClick={() => currentBookId ? void loadBook(currentBookId) : appendLog("当前没有已加载的书籍。")} aria-label="刷新当前书籍">↻</button>
            <button className="button button-secondary compact" type="button" onClick={logout}>退出</button>
          </div>
          <div className="connection-strip">
            <strong className="status-dot-text"><span className="status-dot"></span>已连接</strong>
          </div>
        </header>

        <main className="app-main">
          {route === "home" ? (
            <HomePage
              books={books}
              counts={statusCounts}
              currentBookId={currentBookId}
              currentBook={currentBook}
              filter={activeBookFilter}
              onFilter={setActiveBookFilter}
              onLoadBook={(bookId) => void loadBook(bookId)}
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
            />
          ) : null}

          {route === "admin" && isAdmin ? (
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

function NavLink({ route, activeRoute, label, icon, onNavigate }: { route: Route; activeRoute: Route; label: string; icon: string; onNavigate: (route: Route) => void }) {
  return (
    <a href={`#/${route}`} className={activeRoute === route ? "active" : ""} onClick={(event) => { event.preventDefault(); onNavigate(route); }}>
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
  onNavigate: (route: Route) => void;
}) {
  const filteredBooks = props.books.filter((book) => props.filter === "all" || String(book.status).toLowerCase() === props.filter);
  return (
    <section className="page-view active">
      <div className="home-grid">
        <section className="home-command-panel">
          <div>
            <p className="eyebrow">Library</p>
            <h1>书库总览</h1>
          </div>
          <div className="home-actions">
            <button className="button button-primary" type="button" onClick={() => props.onNavigate("translate")}>上传并翻译</button>
            <button className="button button-secondary" type="button" onClick={() => props.onNavigate("read")}>打开阅读器</button>
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
            <div><h2>书籍</h2><p>选择一本书后，翻译和阅读视图会同步更新。</p></div>
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
              <article key={book.id} className={`book-row${props.currentBookId === book.id ? " active" : ""}`} role="button" tabIndex={0} onClick={() => props.onLoadBook(book.id)}>
                <div className="mini-cover" style={{ background: getBookCoverStyle(book) }}>{bookCoverInitials(book)}</div>
                <div>
                  <h2>{displayBookTitle(book) || "未命名书籍"}</h2>
                  <p>{book.filename} · {sourceLanguageLabel(book.source_language)} · {Math.round((book.progress || 0) * 100)}%</p>
                </div>
                <time>{formatDateTime(book.updated_at || book.created_at)}</time>
                <span className={`book-status ${bookStatusClassName(book.status)}`}>{translateStatus(book.status)}</span>
              </article>
            )) : <div className="empty-state">暂无书籍。上传 EPUB 后会出现在这里。</div>}
          </div>
        </section>
        <aside className="selected-book-panel surface-panel">
          <div className="section-heading"><div><h2>当前书籍</h2><p>选中状态</p></div></div>
          {props.currentBook ? (
            <dl className="metadata-list">
              <div><dt>标题</dt><dd>{displayBookTitle(props.currentBook)}</dd></div>
              <div><dt>文件</dt><dd>{props.currentBook.filename}</dd></div>
              <div><dt>语言</dt><dd>{sourceLanguageLabel(props.currentBook.source_language)} → 中文</dd></div>
              <div><dt>状态</dt><dd><span className={`status-pill ${statusBadgeClass(props.currentBook.status)}`}>{translateStatus(props.currentBook.status)}</span></dd></div>
            </dl>
          ) : <div className="empty-state">请选择一本书，或进入翻译页上传 EPUB。</div>}
        </aside>
      </div>
    </section>
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
                <span aria-hidden="true">⇧</span>
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
              <button className="button button-primary full" type="submit" disabled={!canRun || props.busyAction === "translate"}>开始翻译</button>
              <button className="button button-secondary full" type="button" onClick={props.onResume} disabled={!props.isMemberLike || !canResume}>恢复任务</button>
              <button className="button button-danger full" type="button" onClick={props.onCancel} disabled={!props.isMemberLike || !activeJob}>取消任务</button>
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
                  <div><p className="eyebrow">Progress</p><h2>翻译进度</h2></div>
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
                <div className="section-heading compact-heading"><div><p className="eyebrow">Output</p><h2>导出</h2></div></div>
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
                        <button className="button button-secondary full" type="button" onClick={() => props.onDownload(kind)} disabled={!ready}>下载{translateArtifactKind(kind)}</button>
                      </div>
                    );
                  })}
                </div>
              </section>
              <section className="chapters-panel surface-panel">
                <div className="section-heading"><div><p className="eyebrow">Chapters</p><h2>章节状态</h2></div></div>
                <ChapterTable chapters={props.chapters} />
              </section>
              <section className="log-workspace-panel surface-panel">
                <div className="section-heading compact-heading"><div><p className="eyebrow">Activity</p><h2>活动日志</h2></div></div>
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
          <button className="button button-primary" type="button" onClick={() => props.onNavigate("home")}>回到书库</button>
        </div>
      </section>
    );
  }
  return (
    <section className="page-view active">
      <div className="reader-layout">
        <aside className="reader-sidebar surface-panel">
          <div className="section-heading compact-heading"><div><p className="eyebrow">Reader</p><h2>阅读控制</h2></div></div>
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
          <button className="button button-secondary full" type="button" onClick={props.onExportNotes}>导出笔记</button>
        </aside>
        <section className="reader-panel surface-panel">
          <div className="section-heading"><div><p className="eyebrow">Text</p><h2>在线阅读</h2></div></div>
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
                  {props.isMemberLike && segmentId ? <button className="text-button reader-note-button" type="button" onClick={() => props.onCreateNote(segmentId)}>{Number(segment.noteCount ?? segment.note_count ?? 0) > 0 ? `笔记 ${segment.noteCount ?? segment.note_count}` : "添加笔记"}</button> : null}
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
                {props.isMemberLike && segmentIdOf(props.selectedSegment) ? <button className="text-button" type="button" onClick={() => props.onCreateNote(segmentIdOf(props.selectedSegment)!)}>新建笔记</button> : null}
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
          <div className="section-heading"><div><p className="eyebrow">Admin</p><h2>用户管理</h2></div></div>
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
          <div className="section-heading compact-heading"><div><p className="eyebrow">Create</p><h2>新建用户</h2></div></div>
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
  return <article><strong>{translateArtifactKind(kind)}</strong><span>{status} · {size ? formatBytes(size) : "等待生成"}</span></article>;
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
  if (["home", "translate", "read", "admin"].includes(route)) {
    return route as Route;
  }
  return "home";
}

function updateBookIdSearch(bookId: number) {
  const url = new URL(window.location.href);
  url.searchParams.set("bookId", String(bookId));
  window.history.replaceState({}, "", url);
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
