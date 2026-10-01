import { __ } from "./i18n.js";

const PREFIX = "/api/method/pibiassistant.pibiassistant_chat.api.";
const TIMEOUT_MS = 60000;
const UPLOAD_TIMEOUT_MS = 180000;
const TECHNICAL_TYPES = new Set([
  "AppNotInstalledError",
  "ImportError",
  "ModuleNotFoundError",
  "AttributeError",
  "KeyError",
  "TypeError",
  "NameError",
  "SyntaxError",
]);
const TECHNICAL_TEXT =
  /Failed to get method for command|has no attribute|Traceback \(most recent call last\)|ModuleNotFoundError|ImportError|AttributeError|Internal Server Error|DoesNotExistError:.*\bmodule\b/i;
const ENTITIES = { "&amp;": "&", "&lt;": "<", "&gt;": ">", "&quot;": '"', "&#39;": "'", "&nbsp;": " " };

export class ApiError extends Error {
  constructor(message, { status = 0, kind = "server", detail = null } = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.kind = kind;
    this.detail = detail;
  }
}

function stripTags(text) {
  let prev;
  let out = String(text);
  do {
    prev = out;
    out = out.replace(/<[^>]*>/g, "");
  } while (out !== prev);
  return out.replace(/&(?:amp|lt|gt|quot|#39|nbsp);/g, (m) => ENTITIES[m]);
}

function serverMessage(body) {
  if (!body || typeof body._server_messages !== "string") return "";
  try {
    const first = JSON.parse(body._server_messages)[0];
    const text = JSON.parse(first).message;
    return stripTags(text).replace(/^\s*\[HTTP_\d+\]\s*/, "").trim();
  } catch {
    return "";
  }
}

export function decodeError(status, body) {
  const b = body && typeof body === "object" ? body : {};
  const excType = typeof b.exc_type === "string" ? b.exc_type : "";
  const marker = [excType, b.exception, b.exc].filter((v) => typeof v === "string").join(" ");
  if (status === 401 || (status === 403 && /CSRFTokenError|SessionStopped/.test(marker))) {
    return { kind: "session", message: __("Your session has expired. Reload the page to sign in again.") };
  }
  if (status === 429) {
    return { kind: "server", message: __("AIDA is busy right now. Please try again in a moment.") };
  }
  const text = serverMessage(b);
  const technical = TECHNICAL_TYPES.has(excType) || TECHNICAL_TEXT.test(text);
  const business = status === 417 || excType === "ValidationError" || excType === "PermissionError";
  if (business && text && !technical) return { kind: "validation", message: text };
  return { kind: "server", message: __("AIDA couldn't finish this answer. Please try again.") };
}

let csrf = null;
function csrfToken() {
  if (csrf === null) csrf = String(globalThis.csrf_token || "");
  return csrf;
}

async function request(url, init, timeoutMs) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), timeoutMs);
  let res;
  try {
    res = await fetch(url, {
      ...init,
      credentials: "same-origin",
      signal: ctrl.signal,
      headers: { "X-Frappe-CSRF-Token": csrfToken(), ...init.headers },
    });
  } catch {
    throw new ApiError(__("Couldn't send your message. Check your connection and try again."), {
      kind: "network",
    });
  } finally {
    clearTimeout(timer);
  }
  let body = null;
  try {
    body = await res.json();
  } catch {
    body = null;
  }
  if (!res.ok || (body && body.exc)) {
    const { kind, message } = decodeError(res.status, body);
    throw new ApiError(message, { status: res.status, kind, detail: kind === "validation" ? message : null });
  }
  return body ? body.message : undefined;
}

export function get(name, params) {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== null && v !== undefined) qs.set(k, String(v));
  }
  const query = qs.toString();
  return request(PREFIX + name + (query ? "?" + query : ""), { method: "GET" }, TIMEOUT_MS);
}

export function post(name, body) {
  return request(
    PREFIX + name,
    {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify(body || {}),
    },
    TIMEOUT_MS,
  );
}

export function upload(name, formData) {
  return request(PREFIX + name, { method: "POST", body: formData }, UPLOAD_TIMEOUT_MS);
}

export async function logout() {
  try {
    await request("/api/method/logout", { method: "POST" }, TIMEOUT_MS);
  } catch {
    /* leave for the login page either way */
  }
  location.assign("/login");
}
