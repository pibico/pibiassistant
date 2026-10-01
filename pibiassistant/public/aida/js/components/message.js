import { h, copyText } from "../lib/dom.js";
import { __, getLang } from "../lib/i18n.js";
import { store } from "../lib/store.js";
import { renderInto, safeHref } from "../lib/markdown.js";
import { formatTime, isoOf, stripProvider, tokensPerSecond } from "../lib/format.js";
import { initialOf } from "../lib/greeting.js";
import { icon } from "./icons.js";
import { toolChip, approvalCard } from "./activity.js";
import { respondApproval } from "../lib/chat.js";
import { show as showToast } from "./toast.js";

const AVATAR_SRC = "/assets/pibiassistant/chat/widget/aida-icon.svg";
const BLOCK_HOSTS = new Set(["UL", "OL", "BLOCKQUOTE"]);
const TEXT_HOSTS = /^(P|LI|H[1-6])$/;

function caretHost(body) {
  let el = body.lastElementChild;
  while (el && BLOCK_HOSTS.has(el.tagName) && el.lastElementChild) el = el.lastElementChild;
  return el && TEXT_HOSTS.test(el.tagName) ? el : body;
}

const signature = (m) =>
  [
    m.status,
    m.model,
    m.promptTokens,
    m.completionTokens,
    m.durationMs,
    m.ts,
    m.errorText,
    m.truncated,
    m.retryable,
    (m.tools || []).map((t) => t.id + t.status).join(","),
    (m.approvals || []).map((a) => a.id + a.status).join(","),
  ].join("|");

function avatar(role) {
  if (role === "assistant") {
    return h("img", { class: "aida-avatar aida-avatar--ai", src: AVATAR_SRC, alt: "", width: 48, height: 48 });
  }
  const { user } = store.get();
  return h("div", { class: "aida-avatar aida-avatar--user", "aria-hidden": "true" }, initialOf({ fullName: user.fullName, userId: user.id }));
}

function fileChip(file) {
  const href = safeHref(file.url);
  const children = [icon("file", 14), h("span", { class: "aida-turn__file-name" }, file.name)];
  return href
    ? h("a", { class: "aida-turn__file", href, target: "_blank", rel: "noopener noreferrer" }, children)
    : h("span", { class: "aida-turn__file" }, children);
}

function footerItems(msg, showUserTime) {
  const items = [];
  if (msg.role === "user") {
    if (showUserTime) items.push(timeEl(msg.ts));
    return items;
  }
  const model = stripProvider(msg.model);
  if (model) items.push(h("span", { title: __("Model used") }, model));
  if (msg.status === "streaming") return items;
  const { promptTokens: up, completionTokens: down } = msg;
  if (up || down) {
    items.push(
      h(
        "span",
        { class: "aida-num" },
        h("span", { title: __("Input tokens") }, "↑" + (up ? up.toLocaleString(getLang()) : "–")),
        " ",
        h("span", { title: __("Output tokens") }, "↓" + (down ? down.toLocaleString(getLang()) : "–")),
      ),
    );
  }
  const tps = tokensPerSecond(down, msg.durationMs);
  if (tps) items.push(h("span", { class: "aida-num", title: __("Output speed") }, __("{0} tokens/s", tps)));
  items.push(timeEl(msg.ts));
  if (msg.status === "aborted") items.push(h("span", null, __("Stopped.")));
  return items;
}

function timeEl(ts) {
  return h("time", { class: "aida-num", datetime: isoOf(ts) }, formatTime(ts));
}

export function createTurn(msg, { onRetry } = {}) {
  let current = msg;
  let lastSig = "";
  let lastRendered = null;
  let raf = 0;
  let copyTimer = 0;
  const isAssistant = msg.role === "assistant";

  const label = h("div", { class: "aida-turn__label" }, isAssistant ? __("AIDA") : __("You"));
  const files = h("div", { class: "aida-turn__files", hidden: true });
  const tools = h("div", { class: "aida-activity", hidden: true });
  const approvals = h("div", { class: "aida-approvals", hidden: true });
  const body = h("div", { class: isAssistant ? "aida-turn__body aida-md" : "aida-turn__body" });
  const notice = h("div", { class: "aida-turn__notices" });
  const actions = h("div", { class: "aida-turn__actions" });
  const footer = h("div", { class: "aida-footer", hidden: true });
  const el = h(
    "article",
    { class: ["aida-turn", isAssistant ? "aida-turn--assistant" : "aida-turn--user"] },
    h("div", { class: "aida-turn__avatar" }, avatar(msg.role)),
    h("div", { class: "aida-turn__content" }, label, files, tools, body, approvals, notice, actions, footer),
  );

  function renderBody() {
    raf = 0;
    const m = current;
    if (!isAssistant) {
      body.textContent = m.content;
      body.hidden = !m.content;
      return;
    }
    if (m.status === "streaming" && m.content === "") {
      body.replaceChildren(h("span", { class: "aida-typing", "aria-hidden": "true" }, h("span"), h("span"), h("span")));
      lastRendered = null;
      return;
    }
    body.hidden = !m.content;
    if (lastRendered !== m.content) {
      renderInto(body, m.content);
      lastRendered = m.content;
    } else {
      body.querySelector(".aida-caret")?.remove();
    }
    if (m.status === "streaming") caretHost(body).append(h("span", { class: "aida-caret", "aria-hidden": "true" }));
  }

  function scheduleBody() {
    if (current.status !== "streaming") {
      cancelAnimationFrame(raf);
      renderBody();
    } else if (!raf) {
      raf = requestAnimationFrame(renderBody);
    }
  }

  function copyButton() {
    const done = h("span", { class: "aida-sr-only", role: "status" });
    const btn = h(
      "button",
      { type: "button", class: "aida-icon-btn aida-turn__copy", "aria-label": __("Copy message"), title: __("Copy message") },
      icon("copy", 16),
      done,
    );
    btn.addEventListener("click", async () => {
      if (!(await copyText(current.content))) {
        showToast({ message: __("Couldn't copy to the clipboard."), type: "error" });
        return;
      }
      btn.replaceChildren(icon("check", 16), done);
      done.textContent = __("Copied");
      clearTimeout(copyTimer);
      copyTimer = setTimeout(() => {
        btn.replaceChildren(icon("copy", 16), done);
        done.textContent = "";
      }, 1500);
    });
    return btn;
  }

  function renderNotices() {
    const { streaming } = store.get();
    const m = current;
    const out = [];
    if (m.errorText) {
      const retry =
        onRetry && (m.status === "error" || m.retryable)
          ? h("button", { type: "button", class: "aida-link-btn aida-turn__retry", onClick: onRetry }, __("Try again"))
          : null;
      out.push(h("div", { class: "aida-turn__notice aida-notice is-error", role: "alert" }, icon("alert", 16), h("span", null, m.errorText), retry));
    }
    if (streaming.slow && streaming.key === m.key && m.status === "streaming") {
      out.push(
        h(
          "div",
          { class: "aida-turn__notice aida-notice", role: "status" },
          icon("alert", 16),
          h("span", null, __("AIDA is taking longer than expected. You can wait, or press Stop and try again.")),
        ),
      );
    }
    if (m.truncated) out.push(h("div", { class: "aida-turn__note" }, __("The answer was cut off at the length limit.")));
    notice.replaceChildren(...out);
  }

  function renderActivity() {
    const m = current;
    const list = m.tools || [];
    tools.hidden = !list.length;
    tools.replaceChildren(...list.map(toolChip));
    const cards = m.approvals || [];
    approvals.hidden = !cards.length;
    const busy = store.get().streaming.active;
    approvals.replaceChildren(
      ...cards.map((a) => approvalCard(a, { disabled: busy, onDecide: (id, response) => respondApproval(m.key, id, response) })),
    );
  }

  function renderExtras() {
    const m = current;
    renderActivity();
    renderNotices();
    actions.replaceChildren(...(isAssistant && m.content && m.status !== "streaming" ? [copyButton()] : []));
    const items = footerItems(m, store.get().prefs.showTimestamps);
    footer.hidden = !items.length;
    footer.replaceChildren(...items);
  }

  function refresh() {
    const m = current;
    el.classList.toggle("is-streaming", m.status === "streaming");
    el.classList.toggle("is-error", m.status === "error");
    const sig = signature(m) + "|" + store.get().prefs.showTimestamps + "|" + store.get().streaming.slow + "|" + store.get().streaming.active;
    scheduleBody();
    if (sig !== lastSig) {
      lastSig = sig;
      renderExtras();
    }
  }

  if (msg.files.length) {
    files.hidden = false;
    files.replaceChildren(...msg.files.map(fileChip));
  }

  const unsubscribe = store.subscribe(refresh, ["streaming", "prefs"]);
  refresh();

  return {
    el,
    update(next) {
      current = next;
      refresh();
    },
    destroy() {
      unsubscribe();
      cancelAnimationFrame(raf);
      clearTimeout(copyTimer);
    },
  };
}
