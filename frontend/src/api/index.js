export function createEndpoint(apiBase = "/api") {
  return {
    createBook: () => `${apiBase}/books`,
    listBooks: () => `${apiBase}/books`,
    listProviders: () => `${apiBase}/providers`,
    getBook: (bookId) => `${apiBase}/books/${bookId}`,
    updateTranslatedTitle: (bookId) => `${apiBase}/books/${bookId}/translated-title`,
    startTranslation: (bookId) => `${apiBase}/books/${bookId}/translation-jobs`,
    resumeTranslation: (bookId) => `${apiBase}/books/${bookId}/translation-jobs/resume`,
    cancelTranslation: (jobId) => `${apiBase}/translation-jobs/${jobId}/cancel`,
    exportZh: (bookId) => `${apiBase}/books/${bookId}/exports/zh`,
    exportBilingual: (bookId) => `${apiBase}/books/${bookId}/exports/bilingual`,
    consistencyReport: (bookId) => `${apiBase}/books/${bookId}/reports/consistency`,
    readerInfo: (bookId) => `${apiBase}/books/${bookId}/reader/info`,
    readerChapters: (bookId) => `${apiBase}/books/${bookId}/chapters`,
    readerSegments: (bookId, chapterId, mode) =>
      `${apiBase}/books/${bookId}/chapters/${chapterId}/segments?mode=${encodeURIComponent(mode)}`,
    segmentNotes: (segmentId) => `${apiBase}/segments/${segmentId}/notes`,
    notesExport: (bookId) => `${apiBase}/books/${bookId}/notes/export`,
  };
}

export async function fetchJson(url, options = {}, fetchImpl = globalThis.fetch) {
  const isFormData = options.body instanceof FormData;
  const response = await fetchImpl(url, {
    ...options,
    headers: {
      Accept: "application/json",
      ...(isFormData ? {} : { "Content-Type": "application/json" }),
      ...(options.headers || {}),
    },
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : null;
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

export function normalizeError(error, fallback) {
  if (!error) {
    return fallback;
  }
  if (error instanceof Error && error.message) {
    return error.message;
  }
  return fallback;
}

export function extractFilename(contentDisposition) {
  if (!contentDisposition) {
    return null;
  }
  const match = /filename\*?=(?:UTF-8''|")?([^";]+)/i.exec(contentDisposition);
  return match ? decodeURIComponent(match[1].replace(/"/g, "")) : null;
}
