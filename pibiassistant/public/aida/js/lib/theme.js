let mql = null;
let onChange = null;

function dark() {
  return typeof matchMedia === "function" && matchMedia("(prefers-color-scheme: dark)");
}

export function resolve(theme) {
  if (theme === "light" || theme === "dark") return theme;
  const q = dark();
  return q && q.matches ? "dark" : "light";
}

function paint(theme) {
  if (typeof document === "undefined") return;
  const resolved = resolve(theme);
  document.documentElement.dataset.theme = resolved;
  document.documentElement.style.colorScheme = resolved;
}

function unwatch() {
  if (mql && onChange) mql.removeEventListener("change", onChange);
  mql = null;
  onChange = null;
}

export function apply(theme) {
  unwatch();
  paint(theme);
  if (theme === "auto") {
    mql = dark();
    if (mql && mql.addEventListener) {
      onChange = () => paint("auto");
      mql.addEventListener("change", onChange);
    } else mql = null;
  }
}

export const init = apply;
