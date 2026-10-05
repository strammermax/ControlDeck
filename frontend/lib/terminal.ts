export async function startTerminal(csrfToken: string, signal?: AbortSignal): Promise<boolean> {
  const response = await fetch("/api/termix/session", {method:"POST", headers:{"X-CSRF-Token":csrfToken}, signal});
  if (!response.ok) throw new Error("Termix unavailable");
  const data = await response.json();
  if (data?.ready !== true) throw new Error("Invalid Termix session");
  return true;
}
