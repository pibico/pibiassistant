// Tool activity and approval requests of an assistant turn, as plain data.

const emptyActivity = () => ({ tools: [], approvals: [] });

function approvalFromBlock(block) {
  const interrupt = (Array.isArray(block.interrupts) && block.interrupts[0]) || {};
  const reason = interrupt.reason || {};
  return {
    id: String(block.id || ""),
    toolName: String(block.tool_name || ""),
    input: block.input && typeof block.input === "object" ? block.input : {},
    interruptId: String(interrupt.id || ""),
    action: String(reason.action || block.action || ""),
    description: String(reason.description || block.description || ""),
    status: ["approved", "rejected", "pending"].includes(block.status) ? block.status : "pending",
  };
}

export function activityFromBlocks(blocks) {
  const out = emptyActivity();
  for (const block of Array.isArray(blocks) ? blocks : []) {
    if (!block || typeof block !== "object") continue;
    if (block.type === "tool_call" && !block.isInternal) {
      out.tools.push({
        id: String(block.id || ""),
        name: String(block.tool_name || ""),
        status: ["success", "error"].includes(block.status) ? block.status : "running",
      });
    } else if (block.type === "interaction" && block.interactionType === "approval") {
      out.approvals.push(approvalFromBlock(block));
    }
  }
  return out;
}

export function parseBlocks(raw) {
  if (Array.isArray(raw)) return raw;
  if (typeof raw !== "string" || !raw) return [];
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

const upsert = (list, item) =>
  list.some((x) => x.id === item.id) ? list.map((x) => (x.id === item.id ? { ...x, ...item } : x)) : [...list, item];

export function applyActivityEvent(msg, payload) {
  const tools = msg.tools || [];
  const approvals = msg.approvals || [];
  switch (payload.event) {
    case "tool_call_start":
      return { ...msg, tools: upsert(tools, { id: String(payload.tool_id), name: String(payload.tool_name || ""), status: "running" }) };
    case "tool_call_result":
      return {
        ...msg,
        tools: upsert(tools, {
          id: String(payload.tool_id),
          name: String(payload.tool_name || ""),
          status: payload.status === "error" ? "error" : "success",
        }),
      };
    case "approval_required":
      return {
        ...msg,
        approvals: upsert(approvals, approvalFromBlock({ ...payload, id: payload.tool_id, interactionType: "approval" })),
      };
    default:
      return msg;
  }
}

export const pendingApprovals = (msg) => (msg.approvals || []).filter((a) => a.status === "pending");

// Only the latest turn can still be resumed; the server enforces its own expiry and answers it clearly.
export function expireApprovals(messages) {
  const lastIndex = messages.length - 1;
  return messages.map((m, i) => {
    if (!pendingApprovals(m).length) return m;
    return i !== lastIndex
      ? {
          ...m,
          status: m.status === "awaiting" ? "done" : m.status,
          approvals: m.approvals.map((a) => (a.status === "pending" ? { ...a, status: "expired" } : a)),
        }
      : m;
  });
}

export function decide(msg, toolId, response) {
  const status = response === "rejected" ? "rejected" : "approved";
  return {
    ...msg,
    approvals: (msg.approvals || []).map((a) => (a.id === toolId && a.status === "pending" ? { ...a, status, response } : a)),
  };
}

// Responses for every approval of the turn, sent in one resume call; undecided ones are rejected by the server.
export function responsesFor(msg) {
  return (msg.approvals || [])
    .filter((a) => a.response && a.interruptId)
    .map((a) => ({ interruptId: a.interruptId, response: a.response }));
}
