import http from "node:http";
import { pathToFileURL } from "node:url";

export const MOCK_MEMBER_USERNAME = "1";
export const MOCK_MEMBER_PASSWORD = "1";
export const MOCK_ADMIN_USERNAME = "2";
export const MOCK_ADMIN_PASSWORD = "2";
export const MOCK_USERNAME = MOCK_MEMBER_USERNAME;
export const MOCK_PASSWORD = MOCK_MEMBER_PASSWORD;

const DEFAULT_PORT = 8080;
const SESSION_COOKIE_NAME = "fanbook_mock";
const NOW = "2026-06-06T09:30:00Z";
const mockAccounts = [
  {
    id: 1,
    username: MOCK_MEMBER_USERNAME,
    password: MOCK_MEMBER_PASSWORD,
    email: "reader@example.test",
    roles: ["MEMBER"],
  },
  {
    id: 2,
    username: MOCK_ADMIN_USERNAME,
    password: MOCK_ADMIN_PASSWORD,
    email: "admin@example.test",
    roles: ["ADMIN"],
  },
];

const books = [];

const chapters = [
  { id: 1, chapterOrder: 1, title: "A Room Full of Marginalia", total_segments: 120, translated_segments: 118, failed_segments: 0 },
  { id: 2, chapterOrder: 2, title: "The Translator Arrives Late", total_segments: 160, translated_segments: 130, failed_segments: 2 },
  { id: 3, chapterOrder: 3, title: "Parallel Notes", total_segments: 180, translated_segments: 92, failed_segments: 1 },
];

const bookDetail = {
  book: {
    id: 42,
    title: "The Memory Archive",
    translated_title: "记忆档案馆",
    filename: "memory-archive.epub",
    source_language: "en",
    status: "running",
    created_at: NOW,
    updated_at: NOW,
  },
  current_job: {
    job_id: 501,
    book_id: 42,
    status: "running",
    progress: 0.62,
    total_segments: 820,
    translated_segments: 508,
    failed_segments: 3,
    estimated_remaining_seconds: 7600,
  },
  chapters,
  artifacts: [
    { id: 1, kind: "zh", status: "ready", filename: "memory-archive.zh.epub", size: 1820000, created_at: NOW },
    { id: 2, kind: "bilingual", status: "ready", filename: "memory-archive.bilingual.epub", size: 2450000, created_at: NOW },
    { id: 3, kind: "consistency_report", status: "pending", filename: "consistency.json", size: null, created_at: NOW },
  ],
};

const segments = [
  {
    id: 1001,
    order: 1,
    type: "paragraph",
    source_text: "In the archive room, every shelf kept a different version of the same afternoon.",
    translated_text: "在档案室里，每一排书架都保存着同一个下午的不同版本。",
    translation_status: "completed",
    note_count: 2,
  },
  {
    id: 1002,
    order: 2,
    type: "paragraph",
    source_text: "The translator marked the sentence twice, first for rhythm and then for doubt.",
    translated_text: "译者把这个句子标了两次，第一次为了节奏，第二次为了疑问。",
    translation_status: "completed",
    note_count: 1,
  },
  {
    id: 1003,
    order: 3,
    type: "paragraph",
    source_text: "Outside, rain made the city sound like pages being turned by an impatient hand.",
    translated_text: "窗外，雨声让整座城市听起来像被一只急切的手翻动的书页。",
    translation_status: "running",
    note_count: 0,
  },
];

const notes = [
  { id: 1, segmentId: 1001, content: "这里的 afternoon 可以保留一点含混感，不要译成具体日期。", created_by: "editor", created_at: NOW },
  { id: 2, segmentId: 1001, content: "“版本”比“副本”更贴合记忆主题。", created_by: "reviewer", created_at: NOW },
];

const providers = {
  default_profile_name: "editorial-gpt",
  providers: [
    {
      profile_name: "editorial-gpt",
      provider_name: "openai-compatible",
      default_model_name: "gpt-5",
      configured: true,
      global_max_concurrency: 3,
      per_chapter_concurrency: 1,
      is_default: true,
    },
  ],
};

const users = {
  users: mockAccounts.map((account) => ({
    id: account.id,
    username: account.username,
    email: account.email,
    enabled: true,
    roles: account.roles,
    created_at: NOW,
    updated_at: NOW,
  })),
};

export function createMockApiServer() {
  return http.createServer(async (request, response) => {
    const url = new URL(request.url ?? "/", "http://127.0.0.1");
    const path = url.pathname.replace(/^\/api/, "");

    if (path === "/auth/csrf") {
      sendJson(response, 200, csrfPayload());
      return;
    }

    if (path === "/auth/login" && request.method === "POST") {
      const payload = await readJson(request);
      const account = findMockAccount(payload.username, payload.password);
      if (account) {
        sendJson(response, 200, currentUserPayload(account), { "Set-Cookie": sessionCookieFor(account) });
        return;
      }
      sendJson(response, 401, { message: "Mock login failed. Use user 1 / 1 or admin 2 / 2." });
      return;
    }

    if (path === "/auth/logout" && request.method === "POST") {
      response.writeHead(204, { "Set-Cookie": `${SESSION_COOKIE_NAME}=; Path=/; Max-Age=0` });
      response.end();
      return;
    }

    if (path === "/auth/me") {
      const account = accountFromRequest(request);
      if (account) {
        sendJson(response, 200, currentUserPayload(account));
        return;
      }
      sendJson(response, 401, { message: "Authentication is required." });
      return;
    }

    const account = accountFromRequest(request);
    if (!account) {
      sendJson(response, 401, { message: "Authentication is required." });
      return;
    }

    routeAuthenticatedRequest(request, response, path, account);
  });
}

function routeAuthenticatedRequest(request, response, path, account) {
  if (path === "/books") {
    sendJson(response, 200, { books, status_counts: { total: 0, running: 0, completed: 0, failed: 0 } });
    return;
  }
  if (path === "/books/42") {
    sendJson(response, 200, bookDetail);
    return;
  }
  if (path === "/providers") {
    sendJson(response, 200, providers);
    return;
  }
  if (path === "/books/42/chapters") {
    sendJson(response, 200, { chapters });
    return;
  }
  if (path === "/books/42/chapters/1/segments") {
    sendJson(response, 200, { chapterId: 1, chapterTitle: "A Room Full of Marginalia", segments });
    return;
  }
  if (path === "/segments/1001/notes") {
    sendJson(response, 200, notes);
    return;
  }
  if (isAdminPath(path) && !account.roles.includes("ADMIN")) {
    sendJson(response, 403, { message: "Admin role is required." });
    return;
  }
  if (path === "/admin/users") {
    sendJson(response, 200, users);
    return;
  }
  const roleUpdateMatch = /^\/admin\/users\/(\d+)\/roles$/.exec(path);
  if (roleUpdateMatch && request.method === "PATCH") {
    const userId = Number(roleUpdateMatch[1]);
    sendJson(response, 200, users.users.find((user) => user.id === userId) || users.users[0]);
    return;
  }
  if (/\/exports\//.test(path) || /\/reports\//.test(path) || /\/notes\/export/.test(path)) {
    sendJson(response, 200, { status: "ready" });
    return;
  }

  sendJson(response, 200, {});
}

function csrfPayload() {
  return {
    token: "mock-token",
    header_name: "X-CSRF-TOKEN",
    parameter_name: "_csrf",
  };
}

function currentUserPayload(account) {
  return {
    id: account.id,
    username: account.username,
    email: account.email,
    roles: account.roles,
    csrf_token: "mock-token",
    csrf_header_name: "X-CSRF-TOKEN",
  };
}

function findMockAccount(username, password) {
  return mockAccounts.find((account) => account.username === String(username ?? "") && account.password === String(password ?? ""));
}

function accountFromRequest(request) {
  const sessionValue = (request.headers.cookie ?? "")
    .split(";")
    .map((cookie) => cookie.trim())
    .find((cookie) => cookie.startsWith(`${SESSION_COOKIE_NAME}=`))
    ?.slice(SESSION_COOKIE_NAME.length + 1);
  return mockAccounts.find((account) => account.username === decodeURIComponent(sessionValue ?? ""));
}

function sessionCookieFor(account) {
  return `${SESSION_COOKIE_NAME}=${encodeURIComponent(account.username)}; Path=/; SameSite=Lax`;
}

function isAdminPath(path) {
  return path === "/admin" || path.startsWith("/admin/");
}

function sendJson(response, status, payload, headers = {}) {
  response.writeHead(status, { "Content-Type": "application/json; charset=utf-8", ...headers });
  response.end(JSON.stringify(payload));
}

function readJson(request) {
  return new Promise((resolve) => {
    let body = "";
    request.on("data", (chunk) => {
      body += chunk;
    });
    request.on("end", () => {
      try {
        resolve(JSON.parse(body || "{}"));
      } catch {
        resolve({});
      }
    });
  });
}

function parseArgs(argv) {
  const options = { port: Number(process.env.FANBOOK_MOCK_API_PORT ?? DEFAULT_PORT) };
  for (const arg of argv) {
    if (arg.startsWith("--port=")) {
      options.port = Number(arg.slice("--port=".length));
    }
  }
  return options;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const options = parseArgs(process.argv.slice(2));
  const server = createMockApiServer();
  server.listen(options.port, "127.0.0.1", () => {
    console.log(`Fanbook mock API: http://127.0.0.1:${options.port}`);
    console.log(`Mock user login: ${MOCK_MEMBER_USERNAME} / ${MOCK_MEMBER_PASSWORD}`);
    console.log(`Mock admin login: ${MOCK_ADMIN_USERNAME} / ${MOCK_ADMIN_PASSWORD}`);
  });
}
