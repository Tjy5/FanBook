export function normalizeRoute(hash) {
  const route = String(hash || "").replace(/^#\/?/, "").trim().toLowerCase();
  return ["home", "translate", "read"].includes(route) ? route : "home";
}

export function routeHash(route) {
  const routeHash = `#/${route}`;
  return `#/${normalizeRoute(routeHash)}`;
}

export function syncRouteHash(route, location = window.location, history = window.history) {
  const nextHash = routeHash(route);
  if (location.hash === nextHash) {
    return;
  }
  const url = new URL(location.href);
  url.hash = nextHash;
  history.replaceState({}, "", url);
}

export function renderRoute(elements, state) {
  const activePage = state.activePage || "home";
  elements.pageViews.forEach((view) => {
    const page = view.dataset.page;
    view.classList.toggle("active", page === activePage);
  });
  elements.routeLinks.forEach((link) => {
    const route = link.dataset.routeLink;
    link.classList.toggle("active", route === activePage);
  });
  if (activePage === "translate") {
    elements.detailPanel.classList.toggle("is-empty", !state.currentBookDetail?.book);
  }
  if (activePage === "read") {
    const hasBook = Boolean(state.currentBookDetail?.book);
    if (elements.readEmptyState) {
      elements.readEmptyState.style.display = hasBook ? "none" : "";
    }
    if (elements.readerLayout) {
      elements.readerLayout.style.display = hasBook ? "" : "none";
    }
  }
}
