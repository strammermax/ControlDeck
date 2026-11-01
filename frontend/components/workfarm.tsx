/** Apps → Workfarm: the Prefect worker dashboard, proxied by ControlDeck under /workfarm/. */
export function Workfarm() {
  return <section className="terminal-panel"><div className="terminal-toolbar"><span>Workfarm</span><a href="/workfarm/" target="_blank" rel="noopener noreferrer">Open in nieuw venster ↗</a></div><iframe className="terminal-frame" src="/workfarm/" title="Workfarm" referrerPolicy="same-origin"/></section>;
}
