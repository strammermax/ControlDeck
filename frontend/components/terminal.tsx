"use client";
import { useEffect, useRef, useState } from "react";
import { startTerminal, syncTerminalTheme } from "../lib/terminal";

export function Terminal({enabled, csrfToken, theme}: {enabled: boolean; csrfToken: string; theme: "dark" | "light"}) {
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [attempt, setAttempt] = useState(0);
  const frame = useRef<HTMLIFrameElement>(null);
  const [frameLoad, setFrameLoad] = useState(0);
  useEffect(() => {
    const target = frame.current?.contentWindow ?? null;
    if (state !== "ready" || !syncTerminalTheme(target, theme)) return;
    // Termix applies its saved theme during React startup and profile changes.
    // The embedded interface follows ControlDeck throughout its lifetime.
    const observer = new MutationObserver(() => syncTerminalTheme(target, theme));
    observer.observe(target!.document.documentElement, {attributes: true, attributeFilter: ["class"]});
    return () => observer.disconnect();
  }, [theme, state, frameLoad]);
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 15000);
    setState("loading");
    startTerminal(csrfToken, controller.signal).then(() => {
      if (controller.signal.aborted) return;
      // Browser sessions stay in HttpOnly cookies; discard stale legacy tokens.
      localStorage.removeItem("jwt");
      setState("ready");
    }).catch(() => setState("failed")).finally(() => clearTimeout(timeout));
    return () => {controller.abort(); clearTimeout(timeout);};
  }, [enabled, csrfToken, attempt]);
  if (!enabled) return <p>Termix is nog niet geïnstalleerd of ingeschakeld. Je beheerder kan de Terminal-provider inrichten.</p>;
  if (state === "loading") return <p role="status">Je beveiligde terminal wordt geopend…</p>;
  if (state === "failed") return <div role="alert"><p>Termix kon niet worden geopend.</p><button onClick={() => setAttempt(attempt + 1)}>Opnieuw proberen</button></div>;
  return <section className="terminal-panel"><div className="terminal-toolbar"><span>Termix · SSH-verbindingen en bestanden</span><a href="/termix/" target="_blank" rel="noopener noreferrer">Open in nieuw venster ↗</a></div><iframe ref={frame} onLoad={() => setFrameLoad(value => value + 1)} className="terminal-frame" src="/termix/" title="Termix terminal" allow="clipboard-read; clipboard-write" referrerPolicy="same-origin"/></section>;
}
