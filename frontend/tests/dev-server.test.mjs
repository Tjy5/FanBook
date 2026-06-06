import assert from "node:assert/strict";
import http from "node:http";
import { join } from "node:path";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

import { contentTypeFor, createFrontendServer, isProxyRequest, resolveStaticFile } from "../dev-server.mjs";
import { createMockApiServer, MOCK_PASSWORD, MOCK_USERNAME } from "../mock-api.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const frontendRoot = join(__dirname, "..");

assert.equal(isProxyRequest("/api/books"), true);
assert.equal(isProxyRequest("/api/books?status=completed"), true);
assert.equal(isProxyRequest("/src/main.tsx"), false);

assert.equal(contentTypeFor("/src/main.tsx"), "text/javascript; charset=utf-8");
assert.equal(contentTypeFor("/src/styles.css"), "text/css; charset=utf-8");
assert.equal(contentTypeFor("/"), "text/html; charset=utf-8");

assert.equal(resolveStaticFile("/", frontendRoot), join(frontendRoot, "index.html"));
assert.equal(resolveStaticFile("/src/main.tsx?v=20260606", frontendRoot), join(frontendRoot, "src", "main.tsx"));
assert.equal(resolveStaticFile("/../README.md", frontendRoot), null);

const listen = (server) =>
  new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => resolve(server.address().port));
  });

const close = (server) =>
  new Promise((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()));
  });

const request = (port, path) =>
  new Promise((resolve, reject) => {
    const req = http.request({ host: "127.0.0.1", port, path }, (res) => {
      res.resume();
      res.on("end", () => resolve(res));
    });
    req.on("error", reject);
    req.end();
  });

let backendPath;
let unexpectedProxyHits = 0;
const configuredBackend = http.createServer((req, res) => {
  backendPath = req.url;
  res.writeHead(204);
  res.end();
});
const unexpectedProxyTarget = http.createServer((req, res) => {
  unexpectedProxyHits += 1;
  res.writeHead(418);
  res.end();
});

const backendPort = await listen(configuredBackend);
const unexpectedPort = await listen(unexpectedProxyTarget);
const frontend = createFrontendServer({ backendUrl: `http://127.0.0.1:${backendPort}` });
const frontendPort = await listen(frontend);

try {
  const res = await request(frontendPort, `http://127.0.0.1:${unexpectedPort}/api/books?status=completed`);

  assert.equal(res.statusCode, 204);
  assert.equal(backendPath, "/api/books?status=completed");
  assert.equal(unexpectedProxyHits, 0);
} finally {
  await close(frontend);
  await close(configuredBackend);
  await close(unexpectedProxyTarget);
}

const requestJson = (port, path, { method = "GET", body, cookie } = {}) =>
  new Promise((resolve, reject) => {
    const payload = body === undefined ? null : JSON.stringify(body);
    const headers = { Accept: "application/json" };
    if (payload) {
      headers["Content-Type"] = "application/json";
      headers["Content-Length"] = Buffer.byteLength(payload);
    }
    if (cookie) {
      headers.Cookie = cookie;
    }
    const req = http.request({ host: "127.0.0.1", port, path, method, headers }, (res) => {
      let responseBody = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        responseBody += chunk;
      });
      res.on("end", () => {
        resolve({
          statusCode: res.statusCode,
          headers: res.headers,
          body: responseBody ? JSON.parse(responseBody) : null,
        });
      });
    });
    req.on("error", reject);
    if (payload) {
      req.write(payload);
    }
    req.end();
  });

const mockApi = createMockApiServer();
const mockApiPort = await listen(mockApi);

try {
  const csrf = await requestJson(mockApiPort, "/api/auth/csrf");
  assert.equal(csrf.statusCode, 200);
  assert.equal(csrf.body.header_name, "X-CSRF-TOKEN");

  const rejected = await requestJson(mockApiPort, "/api/auth/login", {
    method: "POST",
    body: { username: MOCK_USERNAME, password: "wrong" },
  });
  assert.equal(rejected.statusCode, 401);

  const login = await requestJson(mockApiPort, "/api/auth/login", {
    method: "POST",
    body: { username: MOCK_USERNAME, password: MOCK_PASSWORD },
  });
  assert.equal(login.statusCode, 200);
  assert.equal(login.body.username, MOCK_USERNAME);
  assert.deepEqual(login.body.roles, ["MEMBER"]);

  const cookie = login.headers["set-cookie"][0].split(";")[0];
  const books = await requestJson(mockApiPort, "/api/books", { cookie });
  assert.equal(books.statusCode, 200);
  assert.equal(books.body.status_counts.total, 0);
  assert.equal(books.body.books.length, 0);

  const notes = await requestJson(mockApiPort, "/api/segments/1001/notes", { cookie });
  assert.equal(notes.statusCode, 200);
  assert.equal(notes.body.length, 2);
} finally {
  await close(mockApi);
}
