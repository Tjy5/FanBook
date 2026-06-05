import { escapeHtml } from "../utils/html.js";
import { bookCoverInitials, displayBookTitle, getBookCoverStyle, sourceLanguageLabel } from "../utils/book.js";
import { formatDateTime } from "../utils/format.js";
import { bookStatusClass, translateStatus } from "../utils/status.js";

export function renderEmptyState(message) {
  return `<div class="empty-state">${escapeHtml(message)}</div>`;
}

export function renderBookRow(book, currentBookId) {
  const status = String(book.status || "pending").toLowerCase();
  const activeClass = Number(book.id) === Number(currentBookId) ? " active" : "";
  const coverStyle = getBookCoverStyle(book);
  return `
    <article class="book-row${activeClass}" data-book-id="${escapeHtml(book.id)}" role="button" tabindex="0">
      <div class="mini-cover" style="background: ${coverStyle};" aria-hidden="true"><span>${escapeHtml(bookCoverInitials(book))}</span></div>
      <div>
        <h2>${escapeHtml(displayBookTitle(book) || "未命名书籍")}</h2>
        <p>${escapeHtml(book.filename || "-")}</p>
        <span>${escapeHtml(sourceLanguageLabel(book.source_language))} → 中文</span>
      </div>
      <time>${escapeHtml(formatDateTime(book.updated_at || book.created_at))}</time>
      <strong class="book-status ${bookStatusClass(status)}">${escapeHtml(translateStatus(status))}</strong>
    </article>
  `;
}
