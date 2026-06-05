export function statusBadgeClass(status) {
  switch ((status || "").toLowerCase()) {
    case "translated":
    case "completed":
    case "ready":
      return "status-success";
    case "translating":
    case "running":
    case "pending":
    case "queued":
      return "status-running";
    case "failed":
    case "error":
      return "status-failed";
    case "skipped":
      return "status-accent";
    default:
      return "status-neutral";
  }
}

export function translateStatus(status) {
  switch ((status || "").toLowerCase()) {
    case "translated":
    case "completed":
    case "ready":
      return "已翻译";
    case "translating":
    case "running":
      return "翻译中";
    case "failed":
    case "error":
      return "失败";
    case "pending":
    case "queued":
      return "待翻译";
    case "canceled":
      return "已取消";
    case "skipped":
      return "已跳过";
    case "idle":
      return "空闲";
    case "unknown":
      return "未知";
    default:
      return status || "-";
  }
}

export function bookStatusClass(status) {
  switch ((status || "").toLowerCase()) {
    case "running":
    case "pending":
      return "running";
    case "completed":
      return "done";
    case "failed":
      return "failed";
    default:
      return "running";
  }
}
