import { test } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import vm from "node:vm";
import path from "node:path";
import { fileURLToPath } from "node:url";

const src = fs.readFileSync(
	path.join(path.dirname(fileURLToPath(import.meta.url)), "../../chat/widget/widget_streaming.js"),
	"utf8"
);

function setup() {
	const frames = [];
	const state = { raw: undefined, html: "", formats: 0, scrolls: 0 };
	const content = {
		length: 1,
		data(k, v) { if (v === undefined) return state.raw; state.raw = v; return this; },
		html(h) { state.html = h; return this; },
		show() { return this; },
	};
	const stub = { length: 1, find: () => stub, is: () => false, hide() { return this; }, show() { return this; } };
	const finder = (sel) => (sel.includes("pao-message-text") ? content : stub);
	const widget = {
		$widget: { find: (sel) => (sel === ".pao-message-streaming" ? { length: 1, find: finder } : finder(sel)) },
		scroll_to_bottom() { state.scrolls++; },
	};
	const window = {
		requestAnimationFrame: (fn) => frames.push(fn) && frames.length,
		cancelAnimationFrame: () => frames.splice(0),
	};
	const ctx = {
		window,
		PAOCore: { format_message: (t) => { state.formats++; return `<p>${t}</p>`; } },
		__: (s) => s,
	};
	vm.createContext(ctx);
	vm.runInContext(src, ctx);
	return { S: window.PAOWidgetStreaming, widget, state, frames };
}

test("200 synchronous chunks render once per frame and the DOM matches the full text", () => {
	const { S, widget, state, frames } = setup();
	for (let i = 0; i < 200; i++) S.update_streaming_message(widget, "abc ");
	assert.equal(state.formats, 0);
	assert.equal(frames.length, 1);
	frames.shift()();
	assert.equal(state.formats, 1);
	assert.ok(state.html.includes("abc ".repeat(200)));
	assert.equal(state.scrolls, 1);
});

test("cancel_stream_render drops the pending frame", () => {
	const { S, widget, state, frames } = setup();
	S.update_streaming_message(widget, "hola");
	S.cancel_stream_render(widget);
	assert.equal(widget._streamRaf, null);
	assert.equal(frames.length, 0);
	assert.equal(state.formats, 0);
});
