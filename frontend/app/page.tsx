"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { version } from "../package.json";

import { navigation, destinations } from "../lib/navigation";
import { Icon } from "../components/icon";

type Health = { status: string; version: string; uptime_seconds: number };
function uptime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${Math.floor(minutes / 1440) ? `${Math.floor(minutes / 1440)}d ` : ""}${Math.floor(minutes / 60) % 24}h ${minutes % 60}m`;
}

export default function Home() {
  const [active, setActive] = useState("dashboard");
  const [mobile, setMobile] = useState(false);
  const [theme, setTheme] = useState("dark");
  const [health, setHealth] = useState<Health | null>(null);
  const [status, setStatus] = useState("Checking");
  const [refreshing, setRefreshing] = useState(false);
  const nav = useRef<HTMLElement>(null);
  const request = useRef<AbortController | null>(null);
  const hamburger = useRef<HTMLButtonElement>(null);
  const closeMenus = useCallback(() => { nav.current?.querySelectorAll("details[open]").forEach(item => item.removeAttribute("open")); }, []);
  const refresh = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 8000);
    setRefreshing(true);
    try {
      const response = await fetch("/health", { cache: "no-store", signal: controller.signal });
      const data: Health = await response.json();
      if (!response.ok || data.status !== "ok" || typeof data.version !== "string" || typeof data.uptime_seconds !== "number") throw new Error("Invalid health response");
      if (request.current === controller) { setHealth(data); setStatus("Online"); }
    } catch { if (request.current === controller) setStatus("Offline"); }
    finally { clearTimeout(timeout); if (request.current === controller) setRefreshing(false); }
  }, []);
  useEffect(() => {
    const route = () => {
      const id = window.location.hash.slice(1);
      setActive(destinations.some(item => item.id === id) ? id : "dashboard");
      setMobile(false); closeMenus();
    };
    route();
    window.addEventListener("hashchange", route);
    return () => window.removeEventListener("hashchange", route);
  }, [closeMenus]);
  useEffect(() => {
    try { const saved = localStorage.getItem("controldeck-theme"); if (saved === "light" || saved === "dark") setTheme(saved); } catch { /* Storage is optional. */ }
  }, []);
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem("controldeck-theme", theme); } catch { /* Storage is optional. */ }
  }, [theme]);
  useEffect(() => {
    void refresh(); const timer = setInterval(() => void refresh(), 30000);
    return () => { clearInterval(timer); request.current?.abort(); request.current = null; };
  }, [refresh]);
  useEffect(() => {
    const outside = (event: PointerEvent) => { if (!nav.current?.contains(event.target as Node)) closeMenus(); };
    const escape = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      const open = nav.current?.querySelector<HTMLDetailsElement>("details[open]");
      if (open) { open.querySelector("summary")?.focus(); closeMenus(); }
      else if (mobile) { setMobile(false); hamburger.current?.focus(); }
    };
    document.addEventListener("pointerdown", outside); document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [closeMenus, mobile]);
  const destination = destinations.find(item => item.id === active)!;
  return <>
    <a className="skip" href="#workspace">Ga naar inhoud</a>
    <header className="topbar">
      <a className="brand" href="#dashboard"><img src="/controldeck-logo.jpg" alt="" className="logo" /><span><h1>ControlDeck</h1><span className="subtitle">ControlDeck homelab Dashboard</span></span></a>
      <div className="tools">
        <span className="user" title="Aanmelden is nog niet ingericht">▱ <span>User: Guest</span></span>
        <span className={`status ${status.toLowerCase()}`} role="status" title="Bereikbaarheid van de ControlDeck-service">{status === "Online" ? "●" : "△"} {status}</span>
        <span className="uptime" title="Uptime van het ControlDeck-proces">Uptime: {status === "Online" && health ? uptime(health.uptime_seconds) : "—"}</span>
        <button className="refresh" onClick={() => void refresh()} disabled={refreshing} aria-label="Status vernieuwen"><span className={refreshing ? "spin" : ""} aria-hidden="true">⟳</span><span>Refresh</span></button>
        <button className="theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={theme === "dark" ? "Licht thema inschakelen" : "Donker thema inschakelen"}>{theme === "dark" ? "☾" : "☀"}</button>
      </div>
    </header>
    <div className="shell">
      <button ref={hamburger} className="hamburger" aria-expanded={mobile} aria-controls="navigation" onClick={() => setMobile(!mobile)}><span aria-hidden="true">☰</span> {destination.label}</button>
      <nav ref={nav} id="navigation" aria-label="Hoofdnavigatie" className={mobile ? "navigation expanded" : "navigation"}>
        {navigation.map(item => {
          const selected = active === item.id || item.children?.some(([id]) => id === active);
          const contents = <><Icon name={item.id} />{item.label}</>;
          return item.children ? <details className="nav-group" key={item.id} onToggle={event => {
            if (event.currentTarget.open) nav.current?.querySelectorAll("details[open]").forEach(other => { if (other !== event.currentTarget) other.removeAttribute("open"); });
          }}><summary className={selected ? "nav-item active" : "nav-item"}>{contents}<span className="chevron" aria-hidden="true">⌄</span></summary><div className="submenu">{item.children.map(([id, label]) => <a key={id} href={`#${id}`} aria-current={active === id ? "page" : undefined} onClick={() => { setActive(id); setMobile(false); closeMenus(); }}>{label}</a>)}</div></details> : <a className={selected ? "nav-item active" : "nav-item"} key={item.id} href={`#${item.id}`} aria-current={selected ? "page" : undefined}>{contents}</a>;
        })}
      </nav>
      <main id="workspace" tabIndex={-1} className={active === "dashboard" ? "workspace" : "workspace module"}>
        {active === "dashboard" ? <h2 className="sr-only">Dashboard</h2> : <><h2>{destination.label}</h2><p>Dit onderdeel is nog niet ingericht.</p></>}
      </main>
      <footer><p>ControlDeck homelab Dashboard v{health?.version ?? version}</p><a href="https://github.com/strammermax/ControlDeck">Support and contribute to the project</a></footer>
    </div>
  </>;
}
