"use client";

import { useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { version } from "../package.json";
import { firstRoute, getDestinations, href, isActive, type Configuration } from "../lib/navigation";
import { Icon } from "../components/icon";
import { Terminal } from "../components/terminal";
import { Accounts } from "../components/accounts";

type AuthSession = { authenticated: boolean; loginAvailable: boolean; user: { firstName: string; lastName: string; email: string; role: string } | null; csrfToken: string | null };
type UserPreferences = { theme?: "dark" | "light"; lastRoute?: string };

type Health = { status: string; version: string; uptime_seconds: number };
function uptime(seconds: number) {
  const minutes = Math.floor(seconds / 60);
  return `${Math.floor(minutes / 1440) ? `${Math.floor(minutes / 1440)}d ` : ""}${Math.floor(minutes / 60) % 24}h ${minutes % 60}m`;
}

export default function Home() {
  const [auth, setAuth] = useState<AuthSession | null>(null);
  const [authError, setAuthError] = useState(false);
  const [preferencesError, setPreferencesError] = useState(false);
  const preferences = useRef<UserPreferences>({});
  const preferenceUser = useRef<string | null>(null);
  const savedPreferences = useRef("");
  const [config, setConfig] = useState<Configuration | null>(null);
  const [configError, setConfigError] = useState(false);
  const [active, setActive] = useState("");
  const [mobile, setMobile] = useState(false);
  const [theme, setTheme] = useState("dark");
  const [themeReady, setThemeReady] = useState(false);
  const [health, setHealth] = useState<Health | null>(null);
  const [status, setStatus] = useState("Checking");
  const [refreshing, setRefreshing] = useState(false);
  const nav = useRef<HTMLElement>(null);
  const request = useRef<AbortController | null>(null);
  const hamburger = useRef<HTMLButtonElement>(null);
  const closeMenus = useCallback(() => { nav.current?.querySelectorAll("details[open]").forEach(item => item.removeAttribute("open")); }, []);
  const destinations = useMemo(() => config ? getDestinations(config) : [], [config]);
  const refresh = useCallback(async () => {
    request.current?.abort();
    const controller = new AbortController();
    request.current = controller;
    const timeout = setTimeout(() => controller.abort(), 8000);
    setRefreshing(true);
    const current = () => request.current === controller;
    try {
      const sessionResponse = await fetch("/api/session", {cache:"no-store", signal:controller.signal});
      if (!sessionResponse.ok) throw new Error("Session unavailable");
      const session: AuthSession = await sessionResponse.json();
      if (!current()) return;
      setAuth(session); setAuthError(false);
      if (!session.authenticated || !session.user) {
        setConfig(null); setActive(""); setThemeReady(false); preferenceUser.current = null; return;
      }
      if (preferenceUser.current !== session.user.email) {
        const response = await fetch("/api/preferences", {cache:"no-store", signal:controller.signal});
        if (!response.ok) throw new Error("Preferences unavailable");
        const values: UserPreferences = await response.json();
        if (!current()) return;
        preferences.current = values; savedPreferences.current = JSON.stringify(values);
        preferenceUser.current = session.user.email; setThemeReady(false);
      }
      await Promise.all([
        (async () => {
          try {
            const response = await fetch("/health", { cache: "no-store", signal: controller.signal });
            const data: Health = await response.json();
            if (!response.ok || data.status !== "ok" || typeof data.version !== "string" || typeof data.uptime_seconds !== "number") throw new Error("Invalid health response");
            if (current()) { setHealth(data); setStatus("Online"); }
          } catch { if (current()) setStatus("Offline"); }
        })(),
        (async () => {
          try {
            const response = await fetch("/api/config", { cache: "no-store", signal: controller.signal });
            const data: Configuration = await response.json();
            if (!response.ok || data.schemaVersion !== 1 || !data.site || !Array.isArray(data.menu) || !Array.isArray(data.modules)) throw new Error("Invalid configuration");
            if (current()) {
              setConfig(previous => JSON.stringify(previous) === JSON.stringify(data) ? previous : data);
              setConfigError(false);
            }
          } catch { if (current()) setConfigError(true); }
        })(),
      ]);
    } catch { if (current()) setAuthError(true); } finally { clearTimeout(timeout); if (current()) setRefreshing(false); }
  }, []);
  useEffect(() => {
    const route = () => {
      const id = window.location.hash.slice(1) || preferences.current.lastRoute || "";
      setActive(destinations.some(item => item.id === id) ? id : (config ? firstRoute(config.menu) ?? destinations[0]?.id ?? "" : ""));
      setMobile(false); closeMenus();
    };
    route(); window.addEventListener("hashchange", route);
    return () => window.removeEventListener("hashchange", route);
  }, [config, destinations, closeMenus]);
  useEffect(() => {
    if (!config || themeReady) return;
    const initial: string = preferences.current.theme ?? config.site.defaultTheme;
    setTheme(initial); setThemeReady(true);
  }, [config, themeReady]);
  useEffect(() => {
    if (!themeReady) return;
    document.documentElement.dataset.theme = theme;

  }, [theme, themeReady]);
  useEffect(() => {
    void refresh();
    return () => { request.current?.abort(); request.current = null; };
  }, [refresh]);
  useEffect(() => {
    if (!auth?.authenticated || !auth.csrfToken || !themeReady || !active) return;
    const values: UserPreferences = {theme: theme === "light" ? "light" : "dark", lastRoute: active};
    preferences.current = values;
    const serialized = JSON.stringify(values);
    if (serialized === savedPreferences.current) return;
    const timer = setTimeout(async () => {
      try {
        const response = await fetch("/api/preferences", {method:"PUT", headers:{"Content-Type":"application/json", "X-CSRF-Token":auth.csrfToken!}, body:serialized});
        if (!response.ok) throw new Error();
        savedPreferences.current = serialized; setPreferencesError(false);
      } catch { setPreferencesError(true); }
    }, 500);
    return () => clearTimeout(timer);
  }, [active, theme, themeReady, auth?.authenticated, auth?.csrfToken]);
  const refreshSeconds = config?.site.refreshSeconds;
  useEffect(() => {
    // Retry initial failures as well; do not retain an interval from a previous configuration.
    const timer = setInterval(() => void refresh(), (refreshSeconds ?? 30) * 1000);
    return () => clearInterval(timer);
  }, [refresh, refreshSeconds]);
  useEffect(() => {
    if (config) document.title = config.site.title;
  }, [config]);
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
  if (!auth?.authenticated) return <main className="login-page"><section className="login-card">
    <img src="/controldeck-logo.jpg" className="logo" alt=""/><h1>ControlDeck</h1><p>Meld je aan om je homelab te openen.</p>
    {authError ? <><p role="alert">Aanmelden kan momenteel niet worden geladen.</p><button onClick={() => void refresh()}>Opnieuw proberen</button></> : !auth ? <p role="status">Aanmelden laden…</p> : auth.loginAvailable ? <><a className="google-login" href="/auth/google/login">Aanmelden met Google</a><p>Alleen toegestane accounts hebben toegang.</p></> : <p role="status">Google-aanmelding wordt nog ingesteld. De omgeving is gesloten voor bezoekers.</p>}
    {typeof window !== "undefined" && new URLSearchParams(window.location.search).get("login") === "denied" && <p role="alert">Aanmelden is niet toegestaan of kon niet worden afgerond.</p>}
  </section></main>;
  if (!config) return <main className="configuration-loading"><h1>ControlDeck</h1><p role="status">{configError ? "De configuratie kan niet worden geladen. Controleer de instellingen." : "Configuratie laden…"}</p>{configError && <button onClick={() => void refresh()} disabled={refreshing}>Opnieuw proberen</button>}</main>;
  if (!destinations.length) return <main className="configuration-loading"><h1>ControlDeck</h1><p>Er zijn nog geen onderdelen aan je account toegewezen. Neem contact op met je beheerder.</p><button onClick={async () => {await fetch("/api/logout", {method:"POST", headers:{"X-CSRF-Token":auth.csrfToken!}}); void refresh();}}>Uitloggen</button></main>;
  const site = config.site;
  const destination = destinations.find(item => item.id === active) ?? destinations[0];
  const provider = config.providers.find(item => item.id === destination?.provider);
  const navigate = (route?: string) => { if (route) setActive(route); setMobile(false); closeMenus(); };
  return <>
    <a className="skip" href="#workspace">Ga naar inhoud</a>
    <header className="topbar">
      <a className="brand" href={`#${firstRoute(config.menu) ?? destinations[0]?.id}`}><img src={site.logo} alt="" className="logo" /><span><h1>{site.title}</h1><span className="subtitle">{site.subtitle}</span></span></a>
      <div className="tools">
        <span className="user">▱ <span>{`${auth.user?.firstName ?? ""} ${auth.user?.lastName ?? ""}`.trim() || auth.user?.email}</span></span><button className="logout" onClick={async () => { const response = await fetch("/api/logout", {method:"POST", headers:{"X-CSRF-Token":auth.csrfToken!}}); if (response.ok) {setAuth(null); setConfig(null); void refresh();} }}>Uitloggen</button>
        <span className={`status ${status.toLowerCase()}`} role="status" title="Bereikbaarheid van de ControlDeck-service">{status === "Online" ? "●" : "△"} {status}</span>
        <span className="uptime" title="Uptime van het ControlDeck-proces">Uptime: {status === "Online" && health ? uptime(health.uptime_seconds) : "—"}</span>
        <button className="refresh" onClick={() => void refresh()} disabled={refreshing} aria-label="Status vernieuwen"><span className={refreshing ? "spin" : ""} aria-hidden="true">⟳</span><span>Refresh</span></button>
        <button className="theme" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={theme === "dark" ? "Licht thema inschakelen" : "Donker thema inschakelen"}>{theme === "dark" ? "☾" : "☀"}</button>
      </div>
    </header>
    <div className="shell">
      {preferencesError && <p className="config-error" role="alert">Je laatste voorkeuren konden niet worden opgeslagen.</p>}
      {configError && <p className="config-error" role="alert">De gewijzigde configuratie kan niet worden geladen. De laatst geladen instellingen blijven zichtbaar.</p>}
      <button ref={hamburger} className="hamburger" aria-expanded={mobile} aria-controls="navigation" onClick={() => setMobile(!mobile)}><span aria-hidden="true">☰</span> {destination?.label}</button>
      <nav ref={nav} id="navigation" aria-label="Hoofdnavigatie" className={mobile ? "navigation expanded" : "navigation"} style={{"--menu-columns": config.menu.length} as CSSProperties}>
        {config.menu.map(item => {
          const selected = isActive(item, active);
          const contents = <><Icon name={item.icon ?? "dashboard"} />{item.label}</>;
          return item.children ? <details className="nav-group" key={item.id} onToggle={event => {
            if (event.currentTarget.open) nav.current?.querySelectorAll("details[open]").forEach(other => { if (other !== event.currentTarget) other.removeAttribute("open"); });
          }}><summary className={selected ? "nav-item active" : "nav-item"}>{contents}<span className="chevron" aria-hidden="true">⌄</span></summary><div className="submenu">{item.children.map(child => <a key={child.id} href={href(child)} aria-current={child.route === active ? "page" : undefined} onClick={() => navigate(child.route)}>{child.label}</a>)}</div></details> : <a className={selected ? "nav-item active" : "nav-item"} key={item.id} href={href(item)} aria-current={selected ? "page" : undefined} onClick={() => navigate(item.route)}>{contents}</a>;
        })}
      </nav>
      <main id="workspace" tabIndex={-1} className={destination?.view === "empty" ? "workspace" : "workspace module"}>
        {destination?.view === "empty" ? <h2 className="sr-only">{destination.label}</h2> : <>
          <h2>{destination?.label}</h2>
          {destination?.view === "terminal" ? <Terminal key={auth.user?.email} enabled={config.providers.some(p => p.id === "termix" && p.enabled)} csrfToken={auth.csrfToken!}/> : active === "admin/users" && auth.user?.role === "admin" ? <Accounts csrfToken={auth.csrfToken!}/> : active === "admin/providers" ? <div className="provider-list">{config.providers.length ? config.providers.map(item => <section key={item.id} className="provider-card"><h3>{item.label}</h3><p>{item.enabled ? "Ingeschakeld" : "Niet ingericht"}</p>{item.url ? <a href={item.url}>{item.url}</a> : <p>Nog geen adres ingesteld.</p>}</section>) : <p>Er zijn nog geen koppelingen ingesteld.</p>}</div> : <>
            <p>{destination?.description ?? "Dit onderdeel is nog niet ingericht."}</p>
            {provider?.url && <><p>Adres: <a href={provider.url}>{provider.url}</a></p><a className="provider-open" href={provider.url} target="_blank" rel="noopener noreferrer">Open {provider.label} ↗</a><p>Deze koppeling opent de toepassing. Gegevens uit de toepassing volgen later.</p></>}
          </>}
        </>}
      </main>
      <footer><p>{site.footerText} v{health?.version ?? version}</p><a href={site.supportUrl}>{site.supportLabel}</a></footer>
    </div>
  </>;
}
