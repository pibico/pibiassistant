import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const dir = path.join(path.dirname(fileURLToPath(import.meta.url)), "../../chat/widget");

function load(file, extra = {}) {
	const win = { csrf_token: "tok", ...extra };
	const ctx = vm.createContext({ window: win, __: (s) => s, console, ...extra });
	vm.runInContext(fs.readFileSync(path.join(dir, file), "utf8"), ctx, { filename: file });
	return { win, ctx };
}

test("server_error_text reads _server_messages, strips tags, falls back to exception", () => {
	const { win } = load("pao_core.js", { DOMPurify: undefined, showdown: undefined });
	const core = win.PAOCore;
	const body = { _server_messages: JSON.stringify([JSON.stringify({ message: "<b>File type</b> not allowed" })]) };
	assert.equal(core.server_error_text(body), "File type not allowed");
	assert.equal(core.server_error_text({ exception: "frappe.ValidationError: x" }), "frappe.ValidationError: x");
	assert.equal(core.server_error_text(null), "");
	assert.equal(core.server_error_text({ _server_messages: "not json" }), "");
});

test("post_form sends the CSRF header and tolerates a non-JSON body", async () => {
	let seen;
	const fetch = async (url, opts) => {
		seen = { url, opts };
		return { ok: false, status: 502, json: async () => { throw new Error("html"); } };
	};
	const { win } = load("pao_core.js", { fetch });
	const out = await win.PAOCore.post_form("/api/x", "FORM");
	assert.equal(seen.opts.headers["X-Frappe-CSRF-Token"], "tok");
	assert.equal(seen.opts.credentials, "same-origin");
	assert.equal(out.json, null);
	assert.equal(out.res.status, 502);
});

test("rich block placeholders keep their markup", () => {
	const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
	const { win } = load("widget_richblocks.js", { PAOCore: { escape_html: esc } });
	const rb = win.PAOWidgetRichBlocks;
	const m = rb._blocks.mermaid("graph TD; A-->B", {}, rb);
	assert.match(m, /pao-rb-placeholder pao-rb-placeholder-mermaid/);
	assert.match(m, /pao-rb-placeholder-type">graph</);
	const c = rb._blocks.chart(JSON.stringify({ type: "bar", title: "T<" }), {}, rb);
	assert.match(c, /pao-rb-placeholder-chart/);
	assert.match(c, /bar — T&lt;/);
	assert.match(c, /<details class="pao-rb-placeholder-code">/);
});

test("reduced-motion block covers continuous animations and sub-spinner has no inline animation", () => {
	const css = fs.readFileSync(path.join(dir, "widget_messages.css"), "utf8");
	const block = css.slice(css.lastIndexOf("@media (prefers-reduced-motion: reduce)"));
	for (const sel of [".pao-thinking-spinner", ".pao-tool-spinner", ".pao-plan-sub-spinner", ".pao-streaming-cursor", ".pao-processing-dot", ".pao-mic-btn.is-recording"]) {
		assert.ok(block.includes(sel), sel);
	}
	const js = fs.readFileSync(path.join(dir, "widget_streaming.js"), "utf8");
	assert.ok(!/pao-plan-sub-spinner"[^>]*style=/.test(js));
});

test("widget palette has no off-token warm greys", () => {
	for (const f of fs.readdirSync(dir).filter((n) => n.endsWith(".css"))) {
		const css = fs.readFileSync(path.join(dir, f), "utf8");
		assert.ok(!/#(57534C|FBFAF8|26241B|F2EFE6)/i.test(css), f);
	}
});
