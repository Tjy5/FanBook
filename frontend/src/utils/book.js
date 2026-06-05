export function sourceLanguageLabel(value) {
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

export function translateArtifactKind(kind) {
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

export function normalizedTranslatedTitle(book) {
  return String(book?.translated_title || "").trim();
}

export function displayBookTitle(book) {
  const normalizedStatus = String(book?.title_translation_status || "").trim().toLowerCase();
  return normalizedStatus === "completed"
    ? normalizedTranslatedTitle(book) || String(book?.title || "").trim()
    : String(book?.title || "").trim();
}

export function renderTranslatedTitle(book) {
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

export function translateTitleTranslationStatus(status) {
  const normalizedStatus = String(status || "").trim().toLowerCase();
  if (normalizedStatus === "completed") {
    return "已翻译";
  }
  if (normalizedStatus === "failed") {
    return "生成失败";
  }
  return "未翻译";
}

export function bookCoverInitials(book) {
  const title = displayBookTitle(book) || book?.filename || "FB";
  return String(title).trim().slice(0, 2).toUpperCase();
}

export function getBookCoverStyle(book) {
  const id = Number(book?.id) || 0;
  const gradients = [
    "linear-gradient(135deg, #1e3c72, #2a5298)",
    "linear-gradient(135deg, #3a1c71, #d76d77, #ffaf7b)",
    "linear-gradient(135deg, #0f2027, #203a43, #2c5364)",
    "linear-gradient(135deg, #11998e, #38ef7d)",
    "linear-gradient(135deg, #fc466b, #3f5efb)",
    "linear-gradient(135deg, #7f00ff, #e100ff)",
    "linear-gradient(135deg, #ff007f, #ff00ff)",
    "linear-gradient(135deg, #00c6ff, #0072ff)",
    "linear-gradient(135deg, #f12711, #f5af19)",
  ];
  return gradients[id % gradients.length];
}
