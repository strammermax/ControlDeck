export async function startTerminal(csrfToken: string, signal?: AbortSignal): Promise<boolean> {
  const response = await fetch("/api/termix/session", {method:"POST", headers:{"X-CSRF-Token":csrfToken}, signal});
  if (!response.ok) throw new Error("Termix unavailable");
  const data = await response.json();
  if (data?.ready !== true) throw new Error("Invalid Termix session");
  return true;
}

const TERMIX_THEME_CLASSES = ["light", "dark", "dracula", "catppuccin", "nord", "solarized", "tokyo-night", "one-dark", "gruvbox"];

// Termix 2.9.1 uses these root classes and this local preference key.
// Keep the iframe mounted: switching theme must not disconnect terminals.
export function syncTerminalTheme(target: Window | null, theme: string): boolean {
  if (!target || (theme !== "light" && theme !== "dark")) return false;
  try {
    const root = target.document.documentElement;
    if (!root) return false;
    for (const name of TERMIX_THEME_CLASSES) {
      if (name !== theme && root.classList.contains(name)) root.classList.remove(name);
    }
    if (!root.classList.contains(theme)) root.classList.add(theme);
    try { target.localStorage.setItem("vite-ui-theme", theme); } catch { /* Styling still works when storage is unavailable. */ }
    return true;
  } catch { return false; } // Only our same-origin Termix embed can be styled.
}
