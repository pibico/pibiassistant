import { __ } from "./i18n.js";
import { stripStopMarker } from "./format.js";

const TERMINAL = new Set(["stream_complete", "stream_error", "stream_aborted"]);

export function isTerminal(eventName) {
  return TERMINAL.has(eventName);
}

const positive = (v) => (typeof v === "number" && v > 0 ? v : null);

export function applyStreamEvent(msg, payload, now) {
  switch (payload.event) {
    case "stream_start":
      return { ...msg, messageId: payload.message_id || msg.messageId, model: payload.model_id || msg.model };
    case "stream_chunk": {
      if (msg.status !== "streaming") return msg;
      const content =
        typeof payload.accumulated === "string" && payload.accumulated
          ? payload.accumulated
          : msg.content + (payload.chunk || "");
      return content === msg.content ? msg : { ...msg, content };
    }
    case "stream_complete":
      if (msg.status !== "streaming") return msg;
      return {
        ...msg,
        status: "done",
        content: payload.full_response || msg.content,
        model: payload.model_id || msg.model,
        promptTokens: positive(payload.prompt_tokens),
        completionTokens: positive(payload.completion_tokens),
        durationMs: positive(payload.duration_ms),
        truncated: !!payload.truncated,
        ts: now,
        errorText: null,
      };
    case "stream_error":
      if (msg.status !== "streaming") return msg;
      return {
        ...msg,
        status: "error",
        errorText: __("AIDA couldn't finish this answer. Please try again."),
        ts: now,
      };
    case "stream_aborted":
      if (msg.status !== "streaming") return msg;
      return {
        ...msg,
        status: "aborted",
        content: stripStopMarker(msg.content || payload.partial_response || ""),
        ts: now,
      };
    default:
      return msg;
  }
}
