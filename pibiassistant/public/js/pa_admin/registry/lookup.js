export function byData(root, selector, key, value) {
  if (!root) return null;
  return Array.from(root.querySelectorAll(selector)).find((el) => el.dataset[key] === value) || null;
}

export function findTool(ctx, name) {
  return ctx.state.toolsData.find((t) => t.name === name);
}

export function registryHost(ctx) {
  return ctx.root.querySelector('#tool-registry');
}

export function failedHtml(message) {
  return `<div style="padding: 20px; text-align: center; color: var(--red-500);">${message}</div>`;
}

export function withTimeout(promise, ms = 20000) {
  let timer;
  const timeout = new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error('timeout')), ms);
  });
  return Promise.race([promise, timeout]).finally(() => clearTimeout(timer));
}
