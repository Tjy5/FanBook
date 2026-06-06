import { createReadStream, existsSync, statSync } from "node:fs";
import http from "node:http";
import https from "node:https";
import { dirname, extname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const DEFAULT_PORT = 5173;
const DEFAULT_BACKEND_URL = "http://localhost:8080";
const FRONTEND_ROOT = dirname(fileURLToPath(import.meta.url));

const CONTENT_TYPES = new Map([
  [".html", "text/html; charset=utf-8"],
  [".css", "text/css; charset=utf-8"],
  [".js", "text/javascript; charset=utf-8"],
  [".mjs", "text/javascript; charset=utf-8"],
  [".ts", "text/javascript; charset=utf-8"],
  [".tsx", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".png", "image/png"],
  [".jpg", "image/jpeg"],
  [".jpeg", "image/jpeg"],
  [".svg", "image/svg+xml; charset=utf-8"],
  [".ico", "image/x-icon"],
]);

export function isProxyRequest(requestUrl) {
  const pathname = new URL(requestUrl, "http://localhost").pathname;
  return pathname === "/api" || pathname.startsWith("/api/");
}

export function contentTypeFor(requestPath) {
  const pathname = new URL(requestPath, "http://localhost").pathname;
  return CONTENT_TYPES.get(extname(pathname).toLowerCase()) ?? "text/html; charset=utf-8";
}

export function resolveStaticFile(requestUrl, root = FRONTEND_ROOT) {
  const rawPath = requestUrl.split("?")[0].split("#")[0] || "/";
  let pathname;
  try {
    pathname = decodeURIComponent(rawPath);
  } catch {
    return null;
  }

  const segments = pathname.split(/[\\/]+/).filter(Boolean);
  if (pathname.includes("\0") || segments.includes("..")) {
    return null;
  }

  const staticPath = pathname === "/" ? "/index.html" : pathname;
  const candidate = resolve(root, "." + staticPath);
  const relativePath = relative(root, candidate);
  if (relativePath === "" || relativePath.startsWith("..") || isAbsolute(relativePath)) {
    return null;
  }
  return candidate;
}

export function createFrontendServer({ root = FRONTEND_ROOT, backendUrl = DEFAULT_BACKEND_URL } = {}) {
  return http.createServer((request, response) => {
    if (isProxyRequest(request.url ?? "/")) {
      proxyRequest(request, response, backendUrl);
      return;
    }

    const filePath = resolveStaticFile(request.url ?? "/", root);
    if (!filePath) {
      response.writeHead(400, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Bad request");
      return;
    }

    if (!existsSync(filePath) || !statSync(filePath).isFile()) {
      response.writeHead(404, { "Content-Type": "text/plain; charset=utf-8" });
      response.end("Not found");
      return;
    }

    response.writeHead(200, { "Content-Type": contentTypeFor(filePath) });
    createReadStream(filePath).pipe(response);
  });
}

function proxyRequest(request, response, backendUrl) {
  const requestTarget = new URL(request.url ?? "/", "http://localhost");
  const target = new URL(`${requestTarget.pathname}${requestTarget.search}`, backendUrl);
  const client = target.protocol === "https:" ? https : http;
  const headers = { ...request.headers, host: target.host };

  const proxy = client.request(target, { method: request.method, headers }, (proxyResponse) => {
    response.writeHead(proxyResponse.statusCode ?? 502, proxyResponse.headers);
    proxyResponse.pipe(response);
  });

  proxy.on("error", (error) => {
    response.writeHead(502, { "Content-Type": "application/json; charset=utf-8" });
    response.end(JSON.stringify({ error: "backend_unreachable", message: error.message }));
  });

  request.pipe(proxy);
}

function parseArgs(argv) {
  const options = {
    port: Number(process.env.FANBOOK_FRONTEND_PORT ?? DEFAULT_PORT),
    backendUrl: process.env.FANBOOK_BACKEND_URL ?? DEFAULT_BACKEND_URL,
  };

  for (const arg of argv) {
    if (arg.startsWith("--port=")) {
      options.port = Number(arg.slice("--port=".length));
    }
    if (arg.startsWith("--backend=")) {
      options.backendUrl = arg.slice("--backend=".length);
    }
  }

  return options;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  const options = parseArgs(process.argv.slice(2));
  const server = createFrontendServer({ backendUrl: options.backendUrl });
  server.listen(options.port, () => {
    console.log(`Fanbook frontend: http://localhost:${options.port}`);
    console.log(`Proxy /api -> ${options.backendUrl}`);
  });
}
