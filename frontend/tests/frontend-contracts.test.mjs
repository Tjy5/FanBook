import assert from "node:assert/strict";

import { createEndpoint, normalizeError } from "../src/api/index.js";
import { createInitialState, POLL_INTERVAL_MS, PROVIDER_PROFILE_STORAGE_KEY, STORAGE_KEY } from "../src/state.js";
import { normalizeRoute, routeHash } from "../src/router.js";

const memoryStorage = new Map();
const storage = {
  getItem: (key) => memoryStorage.get(key) ?? null,
  setItem: (key, value) => memoryStorage.set(key, String(value)),
  removeItem: (key) => memoryStorage.delete(key),
};
storage.setItem(PROVIDER_PROFILE_STORAGE_KEY, "profile-a");

const state = createInitialState(storage);
assert.equal(STORAGE_KEY, "fanbook.currentBookId");
assert.equal(POLL_INTERVAL_MS, 3000);
assert.equal(state.activePage, "home");
assert.equal(state.selectedProviderProfileName, "profile-a");
assert.deepEqual(state.books, []);
assert.equal(normalizeRoute("#/translate"), "translate");
assert.equal(normalizeRoute("#/missing"), "home");
assert.equal(routeHash("read"), "#/read");

const endpoint = createEndpoint("/api");
assert.equal(endpoint.listBooks(), "/api/books");
assert.equal(endpoint.getBook(7), "/api/books/7");
assert.equal(endpoint.readerSegments(7, 3, "bilingual"), "/api/books/7/chapters/3/segments?mode=bilingual");
assert.equal(normalizeError(new Error("boom"), "fallback"), "boom");
assert.equal(normalizeError(null, "fallback"), "fallback");
