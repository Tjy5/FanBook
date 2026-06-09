import { createServer } from "vite";
import { chromium } from "playwright";
import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { createMockApiServer } from "../mock-api.mjs";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const frontendRoot = path.resolve(__dirname, "..");
const repoRoot = path.resolve(frontendRoot, "..");
const screenshotDir = path.resolve(process.env.FANBOOK_SCREENSHOT_DIR ?? path.join(repoRoot, "assets", "screenshots"));
const viewport = { width: 1440, height: 960 };

const screenshots = [
  {
    route: "library",
    fileName: "fanbook-library.png",
    expectedText: ["我的书架", "Fanbook 演示书"],
  },
  {
    route: "translate",
    fileName: "fanbook-translate.png",
    expectedText: ["上传 EPUB", "翻译进度", "章节状态"],
  },
  {
    route: "read",
    fileName: "fanbook-reader.png",
    expectedText: ["Before the Upload", "左页原文，右页译文"],
  },
  {
    route: "settings",
    fileName: "fanbook-settings.png",
    expectedText: ["个人 AI 设置", "我的模型配置"],
  },
];

const delay = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

function listen(server, host = "127.0.0.1") {
  return new Promise((resolve, reject) => {
    server.once("error", reject);
    server.listen(0, host, () => {
      server.off("error", reject);
      const address = server.address();
      if (!address || typeof address === "string") {
        reject(new Error("Could not resolve server listen address."));
        return;
      }
      resolve(address.port);
    });
  });
}

function closeServer(server) {
  return new Promise((resolve, reject) => {
    server.close((error) => (error ? reject(error) : resolve()));
  });
}

async function startVite(mockApiUrl) {
  const server = await createServer({
    root: frontendRoot,
    logLevel: "silent",
    server: {
      host: "127.0.0.1",
      port: 0,
      strictPort: false,
      proxy: {
        "/api": {
          target: mockApiUrl,
          changeOrigin: true,
        },
      },
    },
  });
  await server.listen();
  const address = server.httpServer?.address();
  if (!address || typeof address === "string") {
    throw new Error("Could not resolve Vite listen address.");
  }
  return { server, url: `http://127.0.0.1:${address.port}` };
}

async function launchChromium() {
  const channel = process.env.FANBOOK_PLAYWRIGHT_CHANNEL;
  const executablePath = process.env.FANBOOK_PLAYWRIGHT_EXECUTABLE_PATH;
  const launchOptions = {
    headless: true,
    ...(channel ? { channel } : {}),
    ...(executablePath ? { executablePath } : {}),
  };

  try {
    return await chromium.launch(launchOptions);
  } catch (error) {
    if (channel || executablePath) {
      throw error;
    }

    const fallback = await findCachedChromiumExecutable();
    if (fallback) {
      return chromium.launch({ headless: true, executablePath: fallback });
    }

    throw new Error(
      [
        "Playwright could not launch Chromium.",
        "Run `npm run screenshots:install-browser` from `frontend/`, or set FANBOOK_PLAYWRIGHT_EXECUTABLE_PATH to an existing Chromium/Chrome executable.",
        `Original error: ${error.message}`,
      ].join("\n")
    );
  }
}

async function findCachedChromiumExecutable() {
  const candidates = [];
  if (process.platform === "win32" && process.env.LOCALAPPDATA) {
    candidates.push({
      root: path.join(process.env.LOCALAPPDATA, "ms-playwright"),
      relativeExecutables: [
        path.join("chrome-win64", "chrome.exe"),
        path.join("chrome-headless-shell-win64", "chrome-headless-shell.exe"),
      ],
    });
  }
  if (process.platform === "darwin" && process.env.HOME) {
    candidates.push({
      root: path.join(process.env.HOME, "Library", "Caches", "ms-playwright"),
      relativeExecutables: [
        path.join("chrome-mac", "Chromium.app", "Contents", "MacOS", "Chromium"),
        path.join("chrome-mac-arm64", "Chromium.app", "Contents", "MacOS", "Chromium"),
      ],
    });
  }
  if (process.platform === "linux" && process.env.HOME) {
    candidates.push({
      root: path.join(process.env.HOME, ".cache", "ms-playwright"),
      relativeExecutables: [
        path.join("chrome-linux", "chrome"),
        path.join("chrome-linux", "headless_shell"),
      ],
    });
  }

  const found = [];
  for (const candidate of candidates) {
    let entries = [];
    try {
      entries = await fs.readdir(candidate.root, { withFileTypes: true });
    } catch {
      continue;
    }
    for (const entry of entries) {
      if (!entry.isDirectory() || !entry.name.startsWith("chromium")) {
        continue;
      }
      const directory = path.join(candidate.root, entry.name);
      for (const relativeExecutable of candidate.relativeExecutables) {
        const executable = path.join(directory, relativeExecutable);
        try {
          const stat = await fs.stat(executable);
          found.push({ executable, modifiedMs: stat.mtimeMs });
        } catch {
          // Keep looking for another cached browser.
        }
      }
    }
  }

  found.sort((a, b) => b.modifiedMs - a.modifiedMs);
  return found[0]?.executable ?? null;
}

async function waitForUi(page, milliseconds = 900) {
  await page.waitForLoadState("networkidle").catch(() => {});
  await delay(milliseconds);
}

async function loginMember(page, frontendUrl) {
  await page.goto(`${frontendUrl}/#/library`, { waitUntil: "domcontentloaded" });
  await waitForUi(page);

  const inputs = page.locator("input");
  if ((await inputs.count()) >= 2) {
    await inputs.nth(0).fill("1");
    await inputs.nth(1).fill("1");
    await page.locator('button[type="submit"]').click();
    await waitForUi(page, 1200);
  }
}

async function openDemoBook(page, frontendUrl) {
  await page.goto(`${frontendUrl}/#/library`, { waitUntil: "domcontentloaded" });
  await waitForUi(page, 1000);

  const openDemoButton = page.getByRole("button", { name: /打开演示书/ }).first();
  if (await openDemoButton.count()) {
    await openDemoButton.click();
    await waitForUi(page, 1600);
  }
}

async function captureRoute(page, frontendUrl, screenshot) {
  const url = `${frontendUrl}/?bookId=demo#/${screenshot.route}`;
  await page.goto(url, { waitUntil: "domcontentloaded" });
  await waitForUi(page, 1200);
  await page.locator(".app-shell").waitFor({ state: "visible", timeout: 10000 });

  const pageText = await page.locator("body").innerText();
  for (const expected of screenshot.expectedText) {
    if (!pageText.includes(expected)) {
      throw new Error(`Expected "${expected}" on #/${screenshot.route}, but it was not found.`);
    }
  }

  const filePath = path.join(screenshotDir, screenshot.fileName);
  await page.screenshot({ path: filePath, fullPage: true });
  await assertPngLooksValid(filePath);
  console.log(`captured ${path.relative(repoRoot, filePath).replaceAll("\\", "/")}`);
}

async function assertPngLooksValid(filePath) {
  const buffer = await fs.readFile(filePath);
  if (buffer.length < 30000) {
    throw new Error(`${filePath} is unexpectedly small (${buffer.length} bytes).`);
  }
  const pngSignature = "89504e470d0a1a0a";
  if (buffer.subarray(0, 8).toString("hex") !== pngSignature) {
    throw new Error(`${filePath} is not a PNG file.`);
  }
  const width = buffer.readUInt32BE(16);
  const height = buffer.readUInt32BE(20);
  if (width < 1200 || height < 800) {
    throw new Error(`${filePath} has unexpected dimensions ${width}x${height}.`);
  }
}

async function main() {
  await fs.mkdir(screenshotDir, { recursive: true });

  const mockApi = createMockApiServer();
  let vite;
  let browser;
  try {
    const mockApiPort = await listen(mockApi);
    const mockApiUrl = `http://127.0.0.1:${mockApiPort}`;
    vite = await startVite(mockApiUrl);

    browser = await launchChromium();
    const page = await browser.newPage({ viewport, deviceScaleFactor: 1 });
    await loginMember(page, vite.url);
    await openDemoBook(page, vite.url);

    for (const screenshot of screenshots) {
      await captureRoute(page, vite.url, screenshot);
    }
  } finally {
    await browser?.close().catch(() => {});
    await vite?.server.close().catch(() => {});
    await closeServer(mockApi).catch(() => {});
  }
}

await main();
