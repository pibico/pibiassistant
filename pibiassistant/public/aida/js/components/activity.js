import { h } from "../lib/dom.js";
import { __ } from "../lib/i18n.js";
import { icon } from "./icons.js";
import { openPanel } from "./panel.js";

const ARGS_MAX_CHARS = 4000;

const TOOL_ICON = { running: "spinner", success: "check-circle", error: "warning-circle" };

function toolLabel(tool) {
  if (tool.status === "running") return __("Using {0}...", tool.name);
  if (tool.status === "error") return __("{0} failed", tool.name);
  return __("Used {0}", tool.name);
}

export function toolChip(tool) {
  const ic = icon(TOOL_ICON[tool.status] || "wrench", 14);
  if (tool.status === "running") ic.classList.add("aida-spin");
  return h("span", { class: ["aida-tool", `aida-tool--${tool.status}`] }, ic, h("span", null, toolLabel(tool)));
}

function argsText(input) {
  const text = JSON.stringify(input, null, 2) || "{}";
  return text.length > ARGS_MAX_CHARS ? text.slice(0, ARGS_MAX_CHARS) + "\n…" : text;
}

const STATUS_LABEL = {
  approved: () => __("Approved"),
  rejected: () => __("Rejected"),
  expired: () => __("This request expired. Ask again to repeat it."),
};

export function approvalCard(approval, { onDecide, disabled = false }) {
  const pending = approval.status === "pending";
  const head = h(
    "div",
    { class: "aida-approval__head" },
    icon("shield-warning", 16),
    h("strong", null, approval.action || approval.toolName),
    approval.toolName ? h("span", { class: "aida-approval__tool" }, approval.toolName) : null,
  );
  const details = h(
    "button",
    {
      type: "button",
      class: "aida-link-btn aida-approval__details",
      "aria-haspopup": "dialog",
      onClick: () => openPanel({
        title: approval.action || approval.toolName || __("Details"),
        body: [
          approval.toolName ? h("p", { class: "aida-approval__tool" }, approval.toolName) : null,
          h("pre", { class: "aida-approval__args" }, argsText(approval.input)),
        ],
        footer: [],
      }),
    },
    icon("info", 14),
    __("Details"),
  );
  const decision = (response, label, cls) =>
    h("button", { type: "button", class: ["aida-btn", cls], disabled, onClick: () => onDecide(approval.id, response) }, label);
  const foot = pending
    ? h(
        "div",
        { class: "aida-approval__actions" },
        decision("rejected", __("Reject"), "aida-btn--outline"),
        decision("session", __("Approve for this chat"), "aida-btn--outline"),
        decision("approve", __("Approve"), "aida-btn--primary"),
      )
    : h("div", { class: ["aida-approval__state", `is-${approval.status}`] }, STATUS_LABEL[approval.status] ? STATUS_LABEL[approval.status]() : "");
  return h(
    "section",
    { class: ["aida-approval", `aida-approval--${approval.status}`], role: "group", "aria-label": approval.action || approval.toolName },
    head,
    pending && approval.description && !approval.description.startsWith("{")
      ? h("p", { class: "aida-approval__summary" }, approval.description)
      : null,
    pending ? h("p", { class: "aida-approval__why" }, __("AIDA wants to run this action on your behalf. Check it before approving.")) : null,
    details,
    foot,
  );
}
