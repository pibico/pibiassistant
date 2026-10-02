import { h, clear } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { formatBytes } from "../lib/format.js";
import * as api from "../lib/api.js";
import { icon } from "./icons.js";
import { show } from "./toast.js";

const ACCEPT = ".pdf,.txt,.md,.png,.jpg,.jpeg,.gif,.webp,.csv,.json,.xml";
export const MAX_FILES = 5;
export const MAX_BYTES = 50 * 1024 * 1024;
const EXTENSIONS = new Set(ACCEPT.split(","));

export function validateFile(file, countSoFar) {
  const name = file.name || "";
  const dot = name.lastIndexOf(".");
  const ext = dot === -1 ? "" : name.slice(dot).toLowerCase();
  if (countSoFar >= MAX_FILES) return { ok: false, reason: "count" };
  if (!EXTENSIONS.has(ext)) return { ok: false, reason: "type" };
  if (file.size > MAX_BYTES) return { ok: false, reason: "size" };
  return { ok: true, reason: null };
}

export function createAttachments({ onChange }) {
  let items = [];
  let nextId = 0;
  const input = h("input", {
    type: "file", multiple: true, accept: ACCEPT, hidden: true, tabindex: "-1",
    onChange: () => { addFiles(input.files); input.value = ""; },
  });
  const el = h("div", { class: "aida-attachments" }, input);

  function render() {
    clear(el);
    el.appendChild(input);
    items.forEach((it) => el.appendChild(chip(it)));
    el.classList.toggle("is-empty", items.length === 0);
  }

  function chip(it) {
    const state = it.status;
    return h("div", { class: ["aida-chip", `is-${state}`], "aria-busy": state === "uploading" ? "true" : null },
      state === "uploading" ? h("span", { class: "aida-spinner aida-chip__spinner", "aria-hidden": "true" }) : icon("paperclip", 14),
      h("span", { class: "aida-chip__name", title: it.name }, it.name),
      h("span", { class: "aida-chip__meta" },
        state === "uploading" ? __("Uploading...") : state === "failed" ? __("Upload failed") : formatBytes(it.size)),
      h("button", {
        type: "button", class: "aida-chip__remove", title: __("Remove file"), "aria-label": __("Remove file"),
        onClick: () => remove(it.id),
      }, icon("x", 14)));
  }

  function update(id, patch) {
    items = items.map((it) => (it.id === id ? { ...it, ...patch } : it));
    render();
    onChange();
  }

  function remove(id) {
    items = items.filter((it) => it.id !== id);
    render();
    onChange();
  }

  async function upload(file, id) {
    try {
      const res = await api.upload("upload_message_file", fileForm(file));
      if (!res || res.success === false || !res.file) throw new Error("upload rejected");
      update(id, { status: "ready", file_url: res.file.file_url, file_name: res.file.file_name || file.name, size: res.file.file_size || file.size });
    } catch (err) {
      console.error("upload_message_file failed", err);
      update(id, { status: "failed" });
      show({ type: "error", message: __("Couldn't upload {0}. Try a smaller file or a different format.", file.name) });
    }
  }

  function fileForm(file) {
    const fd = new FormData();
    fd.append("file", file);
    return fd;
  }

  function addFiles(list) {
    for (const file of Array.from(list || [])) {
      const check = validateFile(file, items.length);
      if (!check.ok) {
        const message = check.reason === "count" ? __("You can attach up to {0} files.", MAX_FILES)
          : check.reason === "size" ? __("{0} is too large (maximum {1}).", file.name, formatBytes(MAX_BYTES))
            : __("Couldn't upload {0}. Try a smaller file or a different format.", file.name);
        show({ type: "error", message });
        if (check.reason === "count") return;
        continue;
      }
      const id = ++nextId;
      items = [...items, { id, name: file.name, size: file.size, status: "uploading", file_url: null, file_name: file.name }];
      upload(file, id);
    }
    render();
    onChange();
  }

  function restore(list) {
    const restored = (list || []).map((f) => ({
      id: ++nextId, name: f.file_name || f.name, size: f.size || 0, status: "ready", file_url: f.file_url, file_name: f.file_name || f.name,
    }));
    items = [...items, ...restored].slice(0, MAX_FILES);
    render();
    onChange();
  }

  render();
  return {
    el,
    openPicker: () => input.click(),
    addFiles,
    getReady: () => items.filter((i) => i.status === "ready").map((i) => ({ name: i.file_name, file_url: i.file_url, file_name: i.file_name, size: i.size })),
    isBusy: () => items.some((i) => i.status === "uploading"),
    hasAny: () => items.length > 0,
    clear: () => { items = []; render(); onChange(); },
    restore,
  };
}
