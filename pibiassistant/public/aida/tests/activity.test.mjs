import test from "node:test";
import assert from "node:assert/strict";
import {
  activityFromBlocks,
  applyActivityEvent,
  decide,
  expireApprovals,
  parseBlocks,
  pendingApprovals,
  responsesFor,
} from "../js/lib/activity.js";
import { applyStreamEvent } from "../js/lib/stream.js";
import { fromHistoryRow } from "../js/lib/format.js";

const blocks = [
  { type: "tool_call", id: "t1", tool_name: "list_documents", status: "success", input: {} },
  {
    type: "interaction",
    interactionType: "approval",
    id: "t2",
    tool_name: "create_document",
    input: { doctype: "Customer" },
    status: "pending",
    interrupts: [{ id: "i1", reason: { type: "approval", action: "Create a document", description: "{}" } }],
  },
];

test("blocks become tool chips and approval cards", () => {
  const a = activityFromBlocks(blocks);
  assert.deepEqual(a.tools, [{ id: "t1", name: "list_documents", status: "success" }]);
  assert.equal(a.approvals.length, 1);
  assert.equal(a.approvals[0].interruptId, "i1");
  assert.equal(a.approvals[0].action, "Create a document");
  assert.equal(a.approvals[0].status, "pending");
});

test("parseBlocks tolerates junk", () => {
  assert.deepEqual(parseBlocks("not json"), []);
  assert.deepEqual(parseBlocks(null), []);
  assert.equal(parseBlocks(JSON.stringify(blocks)).length, 2);
});

test("live events build the same activity", () => {
  let m = { status: "streaming", tools: [], approvals: [] };
  m = applyActivityEvent(m, { event: "tool_call_start", tool_id: "t1", tool_name: "list_documents" });
  assert.equal(m.tools[0].status, "running");
  m = applyActivityEvent(m, { event: "tool_call_result", tool_id: "t1", tool_name: "list_documents", status: "success" });
  assert.equal(m.tools.length, 1);
  assert.equal(m.tools[0].status, "success");
  m = applyActivityEvent(m, {
    event: "approval_required",
    tool_id: "t2",
    tool_name: "create_document",
    input: { a: 1 },
    interrupts: [{ id: "i1", reason: { action: "Create a document", description: "d" } }],
  });
  assert.equal(pendingApprovals(m).length, 1);
});

test("an interrupted completion pauses the turn instead of finishing it", () => {
  const live = { status: "streaming", content: "", tools: [], approvals: [] };
  const next = applyStreamEvent(live, { event: "stream_complete", interrupted: true, full_response: "", blocks }, 1);
  assert.equal(next.status, "awaiting");
  assert.equal(next.approvals.length, 1);
});

test("decisions are collected and sent together", () => {
  let m = { approvals: activityFromBlocks(blocks).approvals };
  m = decide(m, "t2", "approve");
  assert.equal(pendingApprovals(m).length, 0);
  assert.deepEqual(responsesFor(m), [{ interruptId: "i1", response: "approve" }]);
  m = decide({ approvals: activityFromBlocks(blocks).approvals }, "t2", "rejected");
  assert.equal(m.approvals[0].status, "rejected");
});

test("only the latest turn keeps a live approval", () => {
  const old = { status: "awaiting", approvals: activityFromBlocks(blocks).approvals };
  const last = { status: "awaiting", approvals: activityFromBlocks(blocks).approvals };
  const [a, b] = expireApprovals([old, last]);
  assert.equal(a.approvals[0].status, "expired");
  assert.equal(a.status, "done");
  assert.equal(b.approvals[0].status, "pending");
  assert.equal(b.status, "awaiting");
});

test("a stored paused row restores as awaiting with its card", () => {
  const msg = fromHistoryRow({
    name: "M1",
    role: "assistant",
    content: "",
    timestamp: "2026-10-01 10:00:00",
    message_id: "x",
    blocks: JSON.stringify(blocks),
  });
  assert.equal(msg.status, "awaiting");
  assert.equal(msg.approvals.length, 1);
  assert.equal(msg.tools.length, 1);
});
