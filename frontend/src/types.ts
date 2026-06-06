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
