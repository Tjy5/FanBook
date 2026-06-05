import { escapeHtml } from "../utils/html.js";
import { formatDateTime, formatNumber } from "../utils/format.js";
import { statusBadgeClass, translateStatus } from "../utils/status.js";

export function renderReader({ elements, state }) {
  renderReaderChapterOptions({ elements, state, chapters: state.readerChapters });
  renderReaderSegments({ elements, state });
  renderSegmentNotesPanel({ elements, state });
}

export function renderReaderChapterOptions({ elements, state, chapters }) {
  const select = elements.readerChapterSelect;
  if (!select) {
    return;
  }

  const chapterList = Array.isArray(chapters) ? chapters : [];
  if (!chapterList.length) {
    select.disabled = true;
    select.innerHTML = '<option value="">暂无章节</option>';
    if (elements.notesExportButton) {
      elements.notesExportButton.disabled = true;
    }
    return;
  }

  select.disabled = false;
  if (elements.notesExportButton) {
    elements.notesExportButton.disabled = false;
  }
  select.innerHTML = chapterList
    .map((chapter) => {
      const chapterId = pickChapterId(chapter);
      const chapterOrder = Number(chapter?.chapterOrder ?? chapter?.order ?? 0) || 0;
      const title = chapter?.title || `章节 ${chapterOrder || chapterId}`;
      return `<option value="${escapeHtml(chapterId)}">#${escapeHtml(chapterOrder || chapterId)} · ${escapeHtml(title)}</option>`;
    })
    .join("");

  const selectedChapterId = pickReaderChapterId(chapterList, state.selectedReaderChapterId);
  state.selectedReaderChapterId = selectedChapterId;
  if (selectedChapterId) {
    select.value = String(selectedChapterId);
  }
}

export function renderReaderSegments({ elements, state, response = null }) {
  const container = elements.readerSegments;
  if (!container) {
    return;
  }

  const segments = Array.isArray(response?.segments) ? response.segments : state.readerSegments;
  if (!segments.length) {
    container.innerHTML = '<div class="empty-state">当前章节没有可显示的段落。</div>';
    return;
  }

  const mode = elements.readerMode?.value || state.selectedReaderMode || "bilingual";
  state.selectedReaderMode = mode;

  container.innerHTML = segments
    .map((segment) => renderReaderSegment({ state, segment, mode }))
    .join("");
}

export function renderReaderSegment({ state, segment, mode }) {
  const segmentId = pickSegmentId(segment);
  const order = Number(segment?.order ?? 0) || 0;
  const translationStatus = String(segment?.translationStatus || segment?.translation_status || "").trim();
  const noteCount = Number(segment?.noteCount ?? segment?.note_count ?? 0) || 0;
  const activeClass = Number(segmentId) === Number(state.selectedReaderSegmentId) ? " active" : "";
  const layoutClass = mode === "bilingual" ? " bilingual" : " single";
  const sourceText = escapeHtml(segment?.sourceText || segment?.source_text || "暂无原文");
  const translatedText = escapeHtml(segment?.translatedText || segment?.translated_text || "暂无译文");
  const typeLabel = escapeHtml(segment?.type || "segment");
  const noteLabel = noteCount > 0 ? `笔记 ${formatNumber(noteCount)}` : "添加笔记";
  const sourceBlock = `
    <div class="reader-segment-column reader-segment-source">
      <span class="reader-segment-kicker">原文</span>
      <p>${sourceText}</p>
    </div>
  `;
  const translatedBlock = `
    <div class="reader-segment-column reader-segment-translated">
      <span class="reader-segment-kicker">译文</span>
      <p>${translatedText}</p>
    </div>
  `;
  const body = mode === "translated"
    ? translatedBlock
    : mode === "original"
      ? sourceBlock
      : `${sourceBlock}${translatedBlock}`;
  const segmentLabel = escapeHtml(order || segmentId);

  return `
    <article class="reader-segment${layoutClass}${activeClass}">
      <div class="reader-segment-main" data-reader-segment-id="${escapeHtml(segmentId)}" role="button" tabindex="0" aria-label="选择段落 #${segmentLabel}">
        <header class="reader-segment-head">
          <div class="reader-segment-meta">
            <strong>段落 #${segmentLabel}</strong>
            <span>${typeLabel}</span>
            <span class="status-pill ${statusBadgeClass(translationStatus)}">${escapeHtml(translateStatus(translationStatus))}</span>
          </div>
        </header>
        <div class="reader-segment-body">
          ${body}
        </div>
      </div>
      <button class="text-button reader-note-button" type="button" data-create-segment-note="${escapeHtml(segmentId)}">${escapeHtml(noteLabel)}</button>
    </article>
  `;
}

export function renderSegmentNotesPanel({ elements, state }) {
  const panel = elements.segmentNotesPanel;
  if (!panel) {
    return;
  }

  const segment = getSelectedReaderSegment(state);
  const notes = Array.isArray(state.selectedReaderNotes) ? state.selectedReaderNotes : [];
  if (!segment) {
    panel.innerHTML =
      '<div class="segment-notes-empty empty-state">选择一个段落后，笔记会显示在这里。</div>';
    return;
  }

  const sourcePreview = escapeHtml((segment.sourceText || segment.source_text || "").trim() || "暂无原文");
  panel.innerHTML = `
    <div class="segment-notes-header">
      <div>
        <strong>段落 #${escapeHtml(segment.order || segment.segmentOrder || segment.segment_id || segment.segmentId || 0)}</strong>
        <p>${sourcePreview}</p>
      </div>
      <button class="text-button" type="button" data-create-segment-note="${escapeHtml(pickSegmentId(segment))}">新建笔记</button>
    </div>
    <div class="segment-notes-list">
      ${
        notes.length
          ? notes
            .map(
              (note) => `
                <article class="segment-note-card">
                  <header>
                    <strong>${escapeHtml(note.createdBy || note.created_by || "local")}</strong>
                    <time>${escapeHtml(formatDateTime(note.createdAt || note.created_at))}</time>
                  </header>
                  <p>${escapeHtml(note.content || note.note_content || "")}</p>
                </article>
              `
            )
            .join("")
          : '<div class="empty-state">这个段落还没有笔记。</div>'
      }
    </div>
  `;
}

export function pickReaderChapterId(chapters, preferredChapterId) {
  if (!Array.isArray(chapters) || !chapters.length) {
    return null;
  }

  const preferred = Number(preferredChapterId) || null;
  if (preferred && chapters.some((chapter) => Number(pickChapterId(chapter)) === preferred)) {
    return preferred;
  }

  return pickChapterId(chapters[0]);
}

export function pickReaderSegmentId(segments, preferredSegmentId) {
  if (!Array.isArray(segments) || !segments.length) {
    return null;
  }

  const preferred = Number(preferredSegmentId) || null;
  if (preferred && segments.some((segment) => Number(pickSegmentId(segment)) === preferred)) {
    return preferred;
  }

  return pickSegmentId(segments[0]);
}

export function pickChapterId(chapter) {
  return Number(chapter?.chapterId ?? chapter?.id ?? 0) || null;
}

export function pickSegmentId(segment) {
  return Number(segment?.segmentId ?? segment?.id ?? 0) || null;
}

export function getSelectedReaderSegment(state) {
  const segmentId = Number(state.selectedReaderSegmentId) || null;
  if (!segmentId) {
    return null;
  }
  return state.readerSegments.find((segment) => Number(pickSegmentId(segment)) === segmentId) || null;
}
