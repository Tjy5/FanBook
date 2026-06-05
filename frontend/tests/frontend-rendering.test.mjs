import assert from "node:assert/strict";

import { renderBookMetadata, renderTranslate } from "../src/pages/translate.js";

function createFakeElement() {
  return {
    attributes: {},
    className: "",
    disabled: false,
    innerHTML: "",
    textContent: "",
    value: "",
    style: {
      width: "",
      setProperty(name, value) {
        this[name] = value;
      },
    },
    setAttribute(name, value) {
      this.attributes[name] = value;
    },
  };
}

function createElements() {
  const names = [
    "bookMetadata",
    "jobStatusPill",
    "jobProgressNumber",
    "jobProgressBar",
    "overallProgressRing",
    "totalSegments",
    "translatedSegments",
    "failedSegments",
    "remainingSegments",
    "jobProgressLabel",
    "exportList",
    "chaptersList",
    "translationProviderProfileSelect",
    "translationProviderSummary",
    "providerStatusLabel",
    "messageLog",
    "translateButton",
    "resumeButton",
    "stopPollingButton",
    "downloadZhButton",
    "downloadBilingualButton",
    "downloadConsistencyButton",
  ];
  return Object.fromEntries(names.map((name) => [name, createFakeElement()]));
}

function createProviderActions(state) {
  return {
    ensureSelectedProviderProfile() {
      if (!state.selectedProviderProfileName && state.providerProfiles.length) {
        state.selectedProviderProfileName = state.providerProfiles[0].profile_name;
      }
    },
    getSelectedProviderProfile() {
      return state.providerProfiles.find(
        (profile) => profile.profile_name === state.selectedProviderProfileName
      ) || null;
    },
    profileIdentifier(profile) {
      return String(profile?.profile_name || profile?.name || "").trim();
    },
  };
}

const emptyElements = createElements();
const emptyState = {
  activity: [],
  currentBookDetail: null,
  providerProfiles: [],
  selectedProviderProfileName: null,
};

renderTranslate({
  elements: emptyElements,
  state: emptyState,
  providerActions: createProviderActions(emptyState),
});

assert.equal(emptyElements.translateButton.disabled, true);
assert.equal(emptyElements.resumeButton.disabled, true);
assert.equal(emptyElements.stopPollingButton.disabled, true);
assert.equal(emptyElements.downloadZhButton.disabled, true);
assert.equal(emptyElements.downloadBilingualButton.disabled, true);
assert.equal(emptyElements.downloadConsistencyButton.disabled, true);

const runningElements = createElements();
const runningState = {
  activity: [],
  providerProfiles: [
    {
      profile_name: "default",
      provider_name: "OpenAI",
      default_model_name: "gpt-4o",
      configured: true,
      is_default: true,
    },
  ],
  selectedProviderProfileName: "default",
  currentBookDetail: {
    book: {
      id: 7,
      title: "Example",
      filename: "example.epub",
      source_language: "en",
      created_at: "2026-06-05T00:00:00Z",
    },
    current_job: {
      status: "running",
      progress: 0.5,
      total_segments: 10,
      translated_segments: 5,
      failed_segments: 0,
    },
    chapters: [],
    artifacts: [
      {
        kind: "zh",
        status: "ready",
        size: 2048,
      },
    ],
  },
};

renderTranslate({
  elements: runningElements,
  state: runningState,
  providerActions: createProviderActions(runningState),
});

assert.equal(runningElements.translateButton.disabled, true);
assert.equal(runningElements.stopPollingButton.disabled, false);
assert.equal(runningElements.resumeButton.disabled, true);
assert.equal(runningElements.downloadZhButton.disabled, false);
assert.equal(runningElements.downloadBilingualButton.disabled, true);
assert.equal(runningElements.downloadConsistencyButton.disabled, true);

const idleElements = createElements();
const idleState = structuredClone(runningState);
idleState.currentBookDetail.current_job = null;
idleState.currentBookDetail.artifacts = [
  { kind: "bilingual", status: "ready", size: 4096 },
  { kind: "consistency_report", status: "ready", size: 512 },
];

renderTranslate({
  elements: idleElements,
  state: idleState,
  providerActions: createProviderActions(idleState),
});

assert.equal(idleElements.translateButton.disabled, false);
assert.equal(idleElements.stopPollingButton.disabled, true);
assert.equal(idleElements.resumeButton.disabled, true);
assert.equal(idleElements.downloadZhButton.disabled, true);
assert.equal(idleElements.downloadBilingualButton.disabled, false);
assert.equal(idleElements.downloadConsistencyButton.disabled, false);

const metadataElements = createElements();
renderBookMetadata({
  elements: metadataElements,
  book: {
    id: 8,
    title: "Accessible Title",
    filename: "accessible.epub",
    source_language: "en",
    created_at: "2026-06-05T00:00:00Z",
  },
});
assert.match(
  metadataElements.bookMetadata.innerHTML,
  /id="book-title-heading"/,
  "Expected rendered metadata to keep the heading id referenced by the book hero"
);
