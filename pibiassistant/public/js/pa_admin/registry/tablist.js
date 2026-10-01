const KEYS = ['ArrowLeft', 'ArrowRight', 'Home', 'End'];

export function bindTablist(listEl, { tabSelector, onActivate, getTabs }) {
  if (!listEl) return () => {};
  const tabs = () => (getTabs ? getTabs() : Array.from(listEl.querySelectorAll(tabSelector)));

  const handler = (e) => {
    if (!KEYS.includes(e.key)) return;
    const tabEl = e.target.closest(tabSelector);
    if (!tabEl || !listEl.contains(tabEl)) return;
    const all = tabs();
    const current = all.indexOf(tabEl);
    if (current < 0) return;
    e.preventDefault();
    let next = current;
    if (e.key === 'ArrowRight') next = (current + 1) % all.length;
    else if (e.key === 'ArrowLeft') next = (current - 1 + all.length) % all.length;
    else if (e.key === 'Home') next = 0;
    else if (e.key === 'End') next = all.length - 1;
    all[next].focus();
    onActivate(all[next]);
  };

  listEl.addEventListener('keydown', handler);
  return () => listEl.removeEventListener('keydown', handler);
}
