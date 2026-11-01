/** Apps → another web app in a frame, with a link to open it on its own. */
export function EmbeddedApp({ title, src, openSrc = src }: { title: string; src: string; openSrc?: string }) {
  return <section className="terminal-panel"><div className="terminal-toolbar"><span>{title}</span><a href={openSrc} target="_blank" rel="noopener noreferrer">Open in nieuw venster ↗</a></div><iframe className="terminal-frame" src={src} title={title} referrerPolicy="same-origin" allow="clipboard-read; clipboard-write; microphone"/></section>;
}
