export const STORAGE_KEY = "fanbook.currentBookId";
export const PROVIDER_PROFILE_STORAGE_KEY = "fanbook.translationProviderProfile";
export const POLL_INTERVAL_MS = 3000;

export const FALLBACK_PROVIDER_PROFILES = [
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

export function createInitialState(storage = globalThis.localStorage) {
  return {
    currentBookId: null,
    currentBookDetail: null,
    books: [],
    statusCounts: null,
    activeBookFilter: "all",
    pollTimer: null,
    activity: [],
    providerProfiles: [],
    defaultProviderProfileName: null,
    selectedProviderProfileName: storage?.getItem(PROVIDER_PROFILE_STORAGE_KEY) ?? null,
    readerInfo: null,
    readerChapters: [],
    readerSegments: [],
    selectedReaderChapterId: null,
    selectedReaderSegmentId: null,
    selectedReaderMode: "bilingual",
    selectedReaderNotes: [],
    activePage: "home",
  };
}
