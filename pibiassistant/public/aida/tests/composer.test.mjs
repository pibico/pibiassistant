import { test } from "node:test";
import assert from "node:assert/strict";
import { validateFile, MAX_FILES, MAX_BYTES } from "../js/components/attachments.js";
import { pickMime } from "../js/components/mic.js";

test("validateFile accepts allowed extensions case-insensitively", () => {
  assert.equal(validateFile({ name: "A.PDF", size: 10 }, 0).ok, true);
  assert.equal(validateFile({ name: "x.webp", size: 10 }, 4).ok, true);
});

test("validateFile rejects type, size and count", () => {
  assert.equal(validateFile({ name: "x.exe", size: 1 }, 0).reason, "type");
  assert.equal(validateFile({ name: "noext", size: 1 }, 0).reason, "type");
  assert.equal(validateFile({ name: "a.pdf", size: MAX_BYTES + 1 }, 0).reason, "size");
  assert.equal(validateFile({ name: "a.pdf", size: 1 }, MAX_FILES).reason, "count");
});

test("pickMime follows candidate order with webm fallback", () => {
  assert.equal(pickMime(() => true), "audio/webm;codecs=opus");
  assert.equal(pickMime((c) => c === "audio/mp4"), "audio/mp4");
  assert.equal(pickMime(() => false), "audio/webm");
});
