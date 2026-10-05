const modules = ["Dashboard", "Proxmox", "Terminal", "Files", "Media", "Network", "Monitoring", "Bookmarks", "Virtual Apps"];

export default function Home() {
  return <main>
    <p className="eyebrow">HOMELAB CONTROL CENTER</p>
    <h1>ControlDeck</h1>
    <p className="lead">One place for your infrastructure and apps.</p>
    <section aria-labelledby="status"><h2 id="status">The foundation is ready.</h2>
      <p>This first release establishes builds, releases and deployment. Modules and authentication will follow. No homelab systems are connected yet.</p>
      <ul>{modules.map(name => <li key={name}>{name}<span>Planned</span></li>)}</ul>
    </section>
    <footer>Lightweight runtime · Docker &amp; LXC</footer>
  </main>;
}
