"use client";
import { useEffect, useState } from "react";
import { startTerminal } from "../lib/terminal";

export function Terminal({enabled, csrfToken}: {enabled: boolean; csrfToken: string}) {
  const [state, setState] = useState<"loading" | "ready" | "failed">("loading");
  const [attempt, setAttempt] = useState(0);
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
  return <section className="terminal-panel"><div className="terminal-toolbar"><span>Termix · SSH-verbindingen en bestanden</span><a href="/termix/" target="_blank" rel="noopener noreferrer">Open in nieuw venster ↗</a></div><iframe className="terminal-frame" src="/termix/" title="Termix terminal" allow="clipboard-read; clipboard-write" referrerPolicy="same-origin"/></section>;
}
