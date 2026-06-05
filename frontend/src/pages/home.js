import { escapeHtml } from "../utils/html.js";
import { displayBookTitle, sourceLanguageLabel } from "../utils/book.js";
import { formatDateTime, formatNumber } from "../utils/format.js";
import { statusBadgeClass, translateStatus } from "../utils/status.js";
import { renderBookRow, renderEmptyState } from "../components/shared.js";

export function renderHome({ elements, state }) {
  renderBookList({ elements, state });
  renderHomeMetrics({ elements, state });
  renderHomeSelectedBook({ elements, state });
}

export function renderBookList({ elements, state }) {
  renderLibraryTabs({ elements, state });
  if (!state.books.length) {
    elements.bookList.innerHTML = renderEmptyState("暂无书籍。上传 EPUB 后会出现在这里。");
    return;
  }

  const filteredBooks = state.books.filter((book) => {
    if (state.activeBookFilter === "all") {
      return true;
    }
    return String(book.status || "").toLowerCase() === state.activeBookFilter;
  });

  if (!filteredBooks.length) {
    elements.bookList.innerHTML = renderEmptyState("当前筛选下没有书籍。");
    return;
  }

  elements.bookList.innerHTML = filteredBooks
    .map((book) => renderBookRow(book, state.currentBookId))
    .join("");
}

export function renderLibraryTabs({ elements, state }) {
  const counts = state.statusCounts || countBooksByStatus(state.books);
  const tabs = [
    ["all", "全部", counts.total],
    ["running", "进行中", counts.running],
    ["completed", "已完成", counts.completed],
    ["failed", "失败", counts.failed],
  ];
  elements.libraryTabs.innerHTML = tabs
    .map(([filter, label, count]) => {
      const activeClass = state.activeBookFilter === filter ? " active" : "";
      return `<button class="tab-button${activeClass}" type="button" data-filter="${filter}">${label} <span>${formatNumber(count)}</span></button>`;
    })
    .join("");
}

export function countBooksByStatus(books) {
  return books.reduce(
    (counts, book) => {
      counts.total += 1;
      const status = String(book.status || "").toLowerCase();
      if (status === "running") {
        counts.running += 1;
      } else if (status === "completed") {
        counts.completed += 1;
      } else if (status === "failed") {
        counts.failed += 1;
      }
      return counts;
    },
    { total: 0, running: 0, completed: 0, failed: 0 }
  );
}

export function renderHomeMetrics({ elements, state }) {
  const counts = state.statusCounts || countBooksByStatus(state.books);
  if (elements.homeTotalCount) {
    elements.homeTotalCount.textContent = formatNumber(counts.total);
  }
  if (elements.homeRunningCount) {
    elements.homeRunningCount.textContent = formatNumber(counts.running);
  }
  if (elements.homeCompletedCount) {
    elements.homeCompletedCount.textContent = formatNumber(counts.completed);
  }
  if (elements.homeFailedCount) {
    elements.homeFailedCount.textContent = formatNumber(counts.failed);
  }
}

export function renderHomeSelectedBook({ elements, state }) {
  if (!elements.homeSelectedBook) {
    return;
  }
  const book = state.currentBookDetail?.book;
  if (!book) {
    elements.homeSelectedBook.innerHTML = renderEmptyState("请选择一本书，或进入翻译页上传 EPUB。");
    return;
  }
  const status = String(book.status || "pending").toLowerCase();
  const title = escapeHtml(displayBookTitle(book) || "未命名书籍");
  const filename = escapeHtml(book.filename || "-");
  const lang = escapeHtml(sourceLanguageLabel(book.source_language));
  const created = escapeHtml(formatDateTime(book.created_at));
  elements.homeSelectedBook.innerHTML = `
    <dl class="metadata-list">
      <div><dt>标题</dt><dd>${title}</dd></div>
      <div><dt>文件</dt><dd>${filename}</dd></div>
      <div><dt>语言</dt><dd>${lang} → 中文</dd></div>
      <div><dt>状态</dt><dd><span class="status-pill ${statusBadgeClass(status)}">${escapeHtml(translateStatus(status))}</span></dd></div>
      <div><dt>创建</dt><dd>${created}</dd></div>
    </dl>
  `;
}
