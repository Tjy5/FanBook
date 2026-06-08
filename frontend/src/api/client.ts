import type {
  AdminUser,
  BookDetail,
  BookListResponse,
  ChapterSummary,
  CsrfState,
  CurrentUser,
  ExportArtifact,
  GlossaryAnalysisResult,
  GlossaryImportResult,
  ProviderProfile,
  ReaderSegment,
  Role,
  SegmentNote,
  TranslationJob,
  TranslationPromptProfile,
  TranslationReviewResult,
} from "../types";

type RequestOptions = Omit<RequestInit, "body" | "headers"> & {
  body?: BodyInit | object | null;
  headers?: HeadersInit;
};

export interface LoginPayload {
  username: string;
  password: string;
}

export interface TranslationPayload {
  providerName?: string;
  modelName?: string | null;
  promptProfile?: TranslationPromptProfile;
}

export interface GlossaryAnalysisPayload {
  providerName?: string;
  modelName?: string | null;
  maxSegments?: number;
  persistCandidates?: boolean;
  promptProfile?: TranslationPromptProfile;
}

export interface TranslationReviewPayload {
  providerName?: string;
  modelName?: string | null;
  maxSegments?: number;
  minScore?: number;
  warningCodes?: string[];
  applyChanges?: boolean;
}

export class ApiClient {
  private csrfState: CsrfState | null = null;

  constructor(private readonly apiBase = "/api") {
  }

  endpoints() {
    return createEndpoint(this.apiBase);
  }

  async csrf(): Promise<CsrfState> {
    const response = await this.request<{ token: string; header_name: string }>("/auth/csrf", { method: "GET" }, false);
    this.csrfState = {
      token: response.token,
      headerName: response.header_name,
    };
    return this.csrfState;
  }

  async login(payload: LoginPayload): Promise<CurrentUser> {
    await this.ensureCsrf();
    const user = await this.request<UserResponse>("/auth/login", {
      method: "POST",
      body: payload,
    });
    this.applyUserCsrf(user);
    return normalizeUser(user);
  }

  async logout(): Promise<void> {
    await this.request<void>("/auth/logout", { method: "POST" });
    this.csrfState = null;
  }

  async me(): Promise<CurrentUser> {
    const user = await this.request<UserResponse>("/auth/me", { method: "GET" });
    this.applyUserCsrf(user);
    return normalizeUser(user);
  }

  listUsers(): Promise<{ users: AdminUser[] }> {
    return this.request("/admin/users", { method: "GET" });
  }

  createUser(payload: { username: string; password: string; email?: string; roles: Role[] }): Promise<AdminUser> {
    return this.request("/admin/users", { method: "POST", body: payload });
  }

  updateUserRoles(userId: number, roles: Role[]): Promise<AdminUser> {
    return this.request(`/admin/users/${userId}/roles`, { method: "PATCH", body: { roles } });
  }

  uploadBook(formData: FormData): Promise<{ bookId: number; title: string; status: string; chapters: number; segments: number }> {
    return this.request("/books", { method: "POST", body: formData });
  }

  listBooks(): Promise<BookListResponse> {
    return this.request("/books", { method: "GET" });
  }

  getBook(bookId: number | string): Promise<BookDetail> {
    return this.request(`/books/${bookId}`, { method: "GET" });
  }

  updateTranslatedTitle(bookId: number, translatedTitle: string): Promise<BookDetail> {
    return this.request(`/books/${bookId}/translated-title`, {
      method: "PATCH",
      body: { translated_title: translatedTitle },
    });
  }

  listProviders(): Promise<{ default_profile_name: string | null; providers: ProviderProfile[] }> {
    return this.request("/providers", { method: "GET" });
  }

  startTranslation(bookId: number, payload: TranslationPayload): Promise<TranslationJob> {
    return this.request(`/books/${bookId}/translation-jobs`, { method: "POST", body: payload });
  }

  resumeTranslation(bookId: number, payload: TranslationPayload): Promise<TranslationJob> {
    return this.request(`/books/${bookId}/translation-jobs/resume`, { method: "POST", body: payload });
  }

  cancelTranslation(jobId: number): Promise<TranslationJob> {
    return this.request(`/translation-jobs/${jobId}/cancel`, { method: "POST" });
  }

  reviewTranslation(bookId: number, payload: TranslationReviewPayload): Promise<TranslationReviewResult> {
    return this.request(`/books/${bookId}/translation-review`, { method: "POST", body: payload });
  }

  analyzeGlossary(bookId: number, payload: GlossaryAnalysisPayload): Promise<GlossaryAnalysisResult> {
    return this.request(`/books/${bookId}/translation-glossary-analysis`, { method: "POST", body: payload });
  }

  acceptGlossaryCandidates(bookId: number): Promise<GlossaryImportResult> {
    return this.request(`/books/${bookId}/translation-glossary-candidates/accept`, { method: "POST" });
  }

  generateArtifact(bookId: number, kind: "zh" | "bilingual" | "consistency_report"): Promise<ExportArtifact> {
    const endpoint = kind === "zh"
      ? `/books/${bookId}/exports/zh`
      : kind === "bilingual"
        ? `/books/${bookId}/exports/bilingual`
        : `/books/${bookId}/reports/consistency`;
    return this.request(endpoint, { method: "POST" });
  }

  artifactUrl(bookId: number, kind: "zh" | "bilingual" | "consistency_report"): string {
    if (kind === "zh") {
      return `${this.apiBase}/books/${bookId}/exports/zh`;
    }
    if (kind === "bilingual") {
      return `${this.apiBase}/books/${bookId}/exports/bilingual`;
    }
    return `${this.apiBase}/books/${bookId}/reports/consistency`;
  }

  readerChapters(bookId: number): Promise<{ chapters: ChapterSummary[] }> {
    return this.request(`/books/${bookId}/chapters`, { method: "GET" });
  }

  readerSegments(bookId: number, chapterId: number, mode: string): Promise<{ chapterId: number; chapterTitle: string; segments: ReaderSegment[] }> {
    return this.request(`/books/${bookId}/chapters/${chapterId}/segments?mode=${encodeURIComponent(mode)}`, { method: "GET" });
  }

  segmentNotes(segmentId: number): Promise<SegmentNote[]> {
    return this.request(`/segments/${segmentId}/notes`, { method: "GET" });
  }

  createNote(segmentId: number, content: string): Promise<SegmentNote> {
    return this.request(`/segments/${segmentId}/notes`, {
      method: "POST",
      body: { content, highlightColor: "#fff5db" },
    });
  }

  notesExportUrl(bookId: number): string {
    return `${this.apiBase}/books/${bookId}/notes/export`;
  }

  private async request<T>(path: string, options: RequestOptions = {}, csrf = true): Promise<T> {
    const method = String(options.method || "GET").toUpperCase();
    const unsafe = !["GET", "HEAD", "OPTIONS", "TRACE"].includes(method);
    if (csrf && unsafe) {
      await this.ensureCsrf();
    }

    const isFormData = options.body instanceof FormData;
    const headers = new Headers(options.headers);
    headers.set("Accept", "application/json");
    if (!isFormData && options.body !== undefined && options.body !== null) {
      headers.set("Content-Type", "application/json");
    }
    if (unsafe && this.csrfState) {
      headers.set(this.csrfState.headerName, this.csrfState.token);
    }

    const response = await fetch(`${this.apiBase}${path}`, {
      ...options,
      credentials: "same-origin",
      headers,
      body: isFormData || typeof options.body === "string"
        ? options.body as BodyInit
        : options.body === undefined || options.body === null
          ? undefined
          : JSON.stringify(options.body),
    });

    if (response.status === 204) {
      return undefined as T;
    }

    const contentType = response.headers.get("content-type") || "";
    const payload = contentType.includes("application/json") ? await response.json() : await response.text();
    if (!response.ok) {
      throw new Error(normalizeApiError(payload, response.status));
    }
    return payload as T;
  }

  private async ensureCsrf() {
    if (!this.csrfState) {
      await this.csrf();
    }
  }

  private applyUserCsrf(user: UserResponse) {
    if (user.csrf_token && user.csrf_header_name) {
      this.csrfState = {
        token: user.csrf_token,
        headerName: user.csrf_header_name,
      };
    }
  }
}

interface UserResponse {
  id: number | null;
  username: string;
  email: string | null;
  roles: Role[];
  csrf_token?: string;
  csrf_header_name?: string;
}

export function createEndpoint(apiBase = "/api") {
  return {
    authCsrf: () => `${apiBase}/auth/csrf`,
    authLogin: () => `${apiBase}/auth/login`,
    authLogout: () => `${apiBase}/auth/logout`,
    authMe: () => `${apiBase}/auth/me`,
    createBook: () => `${apiBase}/books`,
    listBooks: () => `${apiBase}/books`,
    listProviders: () => `${apiBase}/providers`,
    getBook: (bookId: number | string) => `${apiBase}/books/${bookId}`,
    updateTranslatedTitle: (bookId: number | string) => `${apiBase}/books/${bookId}/translated-title`,
    startTranslation: (bookId: number | string) => `${apiBase}/books/${bookId}/translation-jobs`,
    resumeTranslation: (bookId: number | string) => `${apiBase}/books/${bookId}/translation-jobs/resume`,
    cancelTranslation: (jobId: number | string) => `${apiBase}/translation-jobs/${jobId}/cancel`,
    reviewTranslation: (bookId: number | string) => `${apiBase}/books/${bookId}/translation-review`,
    glossaryAnalysis: (bookId: number | string) => `${apiBase}/books/${bookId}/translation-glossary-analysis`,
    acceptGlossaryCandidates: (bookId: number | string) => `${apiBase}/books/${bookId}/translation-glossary-candidates/accept`,
    exportZh: (bookId: number | string) => `${apiBase}/books/${bookId}/exports/zh`,
    exportBilingual: (bookId: number | string) => `${apiBase}/books/${bookId}/exports/bilingual`,
    consistencyReport: (bookId: number | string) => `${apiBase}/books/${bookId}/reports/consistency`,
    readerInfo: (bookId: number | string) => `${apiBase}/books/${bookId}/reader/info`,
    readerChapters: (bookId: number | string) => `${apiBase}/books/${bookId}/chapters`,
    readerSegments: (bookId: number | string, chapterId: number | string, mode: string) =>
      `${apiBase}/books/${bookId}/chapters/${chapterId}/segments?mode=${encodeURIComponent(mode)}`,
    segmentNotes: (segmentId: number | string) => `${apiBase}/segments/${segmentId}/notes`,
    notesExport: (bookId: number | string) => `${apiBase}/books/${bookId}/notes/export`,
  };
}

export function normalizeError(error: unknown, fallback: string): string {
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export function extractFilename(contentDisposition: string | null): string | null {
  if (!contentDisposition) {
    return null;
  }
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(contentDisposition);
  return match ? decodeURIComponent(match[1].replace(/"/g, "")) : null;
}

function normalizeApiError(payload: unknown, status: number): string {
  if (typeof payload === "object" && payload !== null) {
    const record = payload as Record<string, unknown>;
    return String(record.message || record.detail || `请求失败，状态码 ${status}。`);
  }
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }
  return `请求失败，状态码 ${status}。`;
}

function normalizeUser(user: UserResponse): CurrentUser {
  return {
    id: user.id,
    username: user.username,
    email: user.email,
    roles: user.roles,
    csrfToken: user.csrf_token,
    csrfHeaderName: user.csrf_header_name,
  };
}
