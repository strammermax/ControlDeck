/** Apps → Workfarm: the Prefect worker dashboard, proxied by ControlDeck under /workfarm/. */
import {workfarmUrl} from '../lib/workfarm';
export function Workfarm({theme}:{theme:'dark'|'light'}) {
  return <section className="terminal-panel"><div className="terminal-toolbar"><span>Workfarm</span><a href={workfarmUrl(theme,false)} target="_blank" rel="noopener noreferrer">Open in nieuw venster ↗</a></div><iframe className="terminal-frame" src={workfarmUrl(theme)} title="Workfarm" referrerPolicy="same-origin"/></section>;
}
