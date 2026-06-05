export function bindEvents({ elements, state, actions }) {
  window.addEventListener("hashchange", () => {
    actions.applyRoute(window.location.hash);
  });

  elements.routeLinks.forEach((link) => {
    link.addEventListener("click", (event) => {
      const route = event.currentTarget.dataset.routeLink;
      if (!route) {
        return;
      }
      event.preventDefault();
      actions.navigateTo(route);
    });
  });

  elements.uploadForm.addEventListener("submit", actions.onUploadSubmit);
  elements.lookupForm.addEventListener("submit", actions.onLookupSubmit);
  elements.translationForm.addEventListener("submit", actions.onTranslateSubmit);
  elements.translationProviderProfileSelect.addEventListener("change", actions.onProviderProfileChange);

  if (elements.bookFileInput) {
    elements.bookFileInput.addEventListener("change", (event) => {
      const file = event.target.files?.[0];
      const tip = document.querySelector("#upload-tip");
      if (!tip) {
        return;
      }
      tip.textContent = file ? file.name : "上传 EPUB";
      if (elements.uploadDropzone) {
        elements.uploadDropzone.style.borderColor = file ? "var(--accent)" : "";
      }
    });
  }

  elements.refreshButton.addEventListener("click", () => {
    if (state.currentBookId) {
      void actions.loadBook(state.currentBookId, { silent: false });
    } else {
      actions.appendLog("当前没有已加载的书籍。");
    }
  });

  elements.useLatestButton.addEventListener("click", () => {
    actions.useRememberedBook();
  });
  elements.stopPollingButton.addEventListener("click", () => {
    void actions.cancelCurrentTranslation();
  });
  elements.resumeButton.addEventListener("click", () => {
    void actions.resumeTranslation();
  });
  elements.downloadZhButton.addEventListener("click", () => {
    void actions.downloadArtifact("zh");
  });
  elements.downloadBilingualButton.addEventListener("click", () => {
    void actions.downloadArtifact("bilingual");
  });
  elements.downloadConsistencyButton.addEventListener("click", () => {
    void actions.downloadArtifact("consistency_report");
  });
  elements.notesExportButton.addEventListener("click", () => {
    void actions.downloadNotesExport();
  });
  elements.homeTranslateAction.addEventListener("click", () => actions.navigateTo("translate"));
  elements.homeReadAction.addEventListener("click", () => actions.navigateTo("read"));
  elements.readerEmptyAction.addEventListener("click", () => actions.navigateTo("home"));
  elements.bookList.addEventListener("click", (event) => {
    void actions.onBookListClick(event);
  });
  elements.bookList.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      void actions.onBookListClick(event);
    }
  });
  elements.libraryTabs.addEventListener("click", (event) => {
    const button = event.target.closest("[data-filter]");
    if (!button) {
      return;
    }
    state.activeBookFilter = button.dataset.filter;
    actions.renderBookList();
  });
  elements.bookMetadata.addEventListener("click", (event) => {
    const button = event.target.closest("[data-edit-translated-title]");
    if (button) {
      void actions.updateTranslatedTitle();
    }
  });
  elements.readerChapterSelect.addEventListener("change", () => {
    state.selectedReaderChapterId = Number(elements.readerChapterSelect.value) || null;
    void actions.loadReaderSegments(state.currentBookId, state.selectedReaderChapterId);
  });
  elements.readerMode.addEventListener("change", () => {
    state.selectedReaderMode = elements.readerMode.value || "bilingual";
    if (state.currentBookId && state.selectedReaderChapterId) {
      void actions.loadReaderSegments(state.currentBookId, state.selectedReaderChapterId);
    }
  });
  elements.readerSegments.addEventListener("click", (event) => {
    actions.onReaderSegmentsClick(event);
  });
  elements.readerSegments.addEventListener("keydown", (event) => {
    if ((event.key === "Enter" || event.key === " ") && !isInteractiveControl(event.target)) {
      event.preventDefault();
      actions.onReaderSegmentsClick(event);
    }
  });
  elements.segmentNotesPanel.addEventListener("click", (event) => {
    actions.onReaderSegmentsClick(event);
  });
}

function isInteractiveControl(target) {
  return Boolean(target?.closest?.("button, input, select, textarea, a, [contenteditable='true']"));
}
