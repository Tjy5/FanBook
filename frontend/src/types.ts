export type Role = "ADMIN" | "MEMBER" | "VIEWER";

export interface CsrfState {
  token: string;
  headerName: string;
}

export interface CurrentUser {
  id: number | null;
  username: string;
  email: string | null;
  roles: Role[];
  csrfToken?: string;
  csrfHeaderName?: string;
}

export interface AdminUser {
  id: number;
  username: string;
  email: string | null;
  enabled: boolean;
  roles: Role[];
  created_at: string | null;
  updated_at: string | null;
}

export interface ProviderProfile {
  profile_name: string;
  provider_name: string;
  default_model_name: string;
  configured: boolean;
  max_requests_per_minute?: number | null;
  global_max_concurrency: number;
  per_chapter_concurrency: number;
  is_default: boolean;
  endpoint?: string | null;
  uses_chat_completions?: boolean | null;
  thinking_mode?: string | null;
  json_mode?: boolean | null;
  min_request_interval_seconds?: number | null;
  request_timeout_seconds?: number | null;
  messaging_prefetch?: number | null;
  messaging_concurrency?: number | null;
  messaging_listener_auto_startup?: boolean | null;
  chunk_target_characters?: number | null;
  max_segments_per_chunk?: number | null;
  max_attempts_per_chunk?: number | null;
  paid_safety_level?: "mock" | "safe" | "warning" | "unsafe" | string | null;
}

export interface BookListItem {
  id: number;
  title: string;
  translated_title?: string | null;
  title_translation_status?: string | null;
  filename: string;
  source_language: string;
  status: string;
  progress: number;
  total_segments: number;
  translated_segments: number;
  failed_segments: number;
  current_job_status?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface StatusCounts {
  total: number;
  running: number;
  completed: number;
  failed: number;
}

export interface BookDto {
  id: number;
  title: string;
  translated_title?: string | null;
  title_translation_status?: string | null;
  filename: string;
  source_language: string;
  status: string;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TranslationJob {
  job_id?: number;
  jobId?: number;
  book_id?: number;
  bookId?: number;
  status: string;
  provider_profile_name?: string | null;
  providerName?: string;
  provider_name?: string;
  modelName?: string;
  model_name?: string;
  progress: number;
  total_segments?: number;
  totalSegments?: number;
  translated_segments?: number;
  translatedSegments?: number;
  failed_segments?: number;
  failedSegments?: number;
  estimated_remaining_seconds?: number | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface TranslationPromptProfile {
  name?: string;
  version?: string;
  styleInstruction?: string;
  translationInstruction?: string;
  reviewInstruction?: string;
  analysisInstruction?: string;
  preserveFormatting?: boolean;
}

export interface TranslationPreflight {
  bookId: number;
  providerName: string;
  modelName: string;
  configured: boolean;
  realProvider: boolean;
  safeToStart: boolean;
  paidSafetyLevel: "mock" | "safe" | "warning" | "unsafe" | string;
  totalSegments: number;
  estimatedChunks: number;
  endpoint: string;
  usesChatCompletions: boolean;
  thinkingMode: string;
  jsonMode: boolean;
  maxConcurrency: number;
  minRequestIntervalSeconds: number;
  requestTimeoutSeconds: number;
  messagingPrefetch: number;
  messagingConcurrency: number;
  messagingListenerAutoStartup: boolean;
  chunkTargetCharacters: number;
  maxSegmentsPerChunk: number;
  maxAttemptsPerChunk: number;
  estimatedMinimumRuntimeSeconds: number;
  warnings: string[];
  recommendations: string[];
}

export interface GlossaryCandidate {
  candidateId?: number | null;
  sourceTerm: string;
  targetTerm?: string | null;
  category?: string | null;
  note?: string | null;
  status: string;
  evidenceCount: number;
  firstSegmentId?: number | null;
}

export interface GlossaryAnalysisResult {
  bookId: number;
  providerName: string;
  modelName: string | null;
  analyzedSegments: number;
  candidateCount: number;
  persistedCandidates: number;
  candidates: GlossaryCandidate[];
}

export interface GlossaryImportResult {
  bookId: number;
  acceptedCandidates: number;
  conflicts: number;
  candidates: GlossaryCandidate[];
}

export interface TranslationReviewSegment {
  segmentId?: number;
  segment_id?: number;
  segmentOrder?: number;
  segment_order?: number;
  score: number;
  warnings: string[];
  reviewed: boolean;
  updated: boolean;
}

export interface TranslationReviewResult {
  bookId?: number;
  book_id?: number;
  providerName?: string;
  provider_name?: string;
  modelName?: string;
  model_name?: string;
  applied: boolean;
  minScore?: number;
  min_score?: number;
  maxSegments?: number;
  max_segments?: number;
  warningCodes?: string[];
  warning_codes?: string[];
  candidateSegments?: number;
  candidate_segments?: number;
  selectedSegments?: number;
  selected_segments?: number;
  reviewedSegments?: number;
  reviewed_segments?: number;
  updatedSegments?: number;
  updated_segments?: number;
  segments: TranslationReviewSegment[];
}

export interface ChapterSummary {
  id?: number;
  chapterId?: number;
  chapterOrder?: number;
  order?: number;
  title: string;
  total_segments?: number;
  totalSegments?: number;
  translated_segments?: number;
  translatedSegments?: number;
  failed_segments?: number;
  failedSegments?: number;
  progress?: number;
}

export interface ExportArtifact {
  id?: number;
  artifactId?: number;
  bookId?: number;
  kind: string;
  status: string;
  filename?: string;
  size?: number | null;
  sizeBytes?: number | null;
  checksum?: string | null;
  created_at?: string | null;
}

export interface BookDetail {
  book: BookDto;
  current_job?: TranslationJob | null;
  chapters: ChapterSummary[];
  artifacts: ExportArtifact[];
}

export interface BookListResponse {
  books: BookListItem[];
  status_counts: StatusCounts;
}

export interface ReaderSegment {
  segmentId?: number;
  id?: number;
  order: number;
  type?: string;
  sourceText?: string;
  source_text?: string;
  translatedText?: string | null;
  translated_text?: string | null;
  translationStatus?: string;
  translation_status?: string;
  noteCount?: number;
  note_count?: number;
}

export interface SegmentNote {
  noteId?: number;
  id?: number;
  bookId?: number;
  segmentId?: number;
  content?: string;
  note_content?: string;
  highlightColor?: string | null;
  createdBy?: string;
  created_by?: string;
  createdAt?: string | null;
  created_at?: string | null;
  updatedAt?: string | null;
  updated_at?: string | null;
}
