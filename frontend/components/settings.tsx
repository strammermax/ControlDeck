"use client";

import { useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { moveItem, orderMenu, type MenuItem } from "../lib/navigation";
import { translate, type Language, type TextKey } from "../lib/i18n";
import { Icon } from "./icon";

export type PersonalSettings = { language: Language; navOrder: string[] };
type Props = { menu: MenuItem[]; settings: PersonalSettings; csrfToken: string; onSaved: (settings: PersonalSettings) => void };

async function store(csrfToken: string, values: Partial<PersonalSettings>) {
  const response = await fetch("/api/preferences", {method:"PUT", headers:{"Content-Type":"application/json", "X-CSRF-Token":csrfToken}, body:JSON.stringify(values)});
  if (!response.ok) throw new Error("Preferences not saved");
}

/** Per-user settings; the server validates and stores them with the user's other preferences. */
export function Settings({ menu, settings, csrfToken, onSaved }: Props) {
  const t = (key: TextKey) => translate(settings.language, key);
  const saved = orderMenu(menu, settings.navOrder).map(item => item.id);
  const [draft, setDraft] = useState<string[] | null>(null);
  const [dragging, setDragging] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const list = useRef<HTMLOListElement>(null);
  const hold = useRef<ReturnType<typeof setTimeout> | null>(null);
  const order = draft ?? saved;
  const items = order.map(id => menu.find(item => item.id === id)).filter((item): item is MenuItem => !!item);
  const defaults = menu.map(item => item.id);
  const changed = draft !== null && draft.join() !== saved.join();

  const save = async (values: Partial<PersonalSettings>) => {
    setBusy(true); setMessage("");
    try {
      await store(csrfToken, values);
      onSaved({...settings, ...values}); setDraft(null); setMessage(t("saved"));
    } catch { setMessage(t("saveFailed")); } finally { setBusy(false); }
  };
  const move = (from: number, to: number) => { if (to >= 0 && to < order.length && from !== to) setDraft(moveItem(order, from, to)); };
  const startDrag = (event: ReactPointerEvent, id: string) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    const begin = () => { setDragging(id); list.current?.setPointerCapture?.(event.pointerId); };
    // Touch needs a long press so that normal scrolling keeps working.
    if (event.pointerType === "touch") hold.current = setTimeout(begin, 350); else { event.preventDefault(); begin(); }
  };
  const drag = (event: ReactPointerEvent) => {
    if (!dragging) return;
    const target = document.elementFromPoint(event.clientX, event.clientY)?.closest<HTMLElement>("[data-nav-id]");
    const id = target?.dataset.navId;
    if (id && id !== dragging) move(order.indexOf(dragging), order.indexOf(id));
  };
  const stopDrag = () => { if (hold.current) clearTimeout(hold.current); hold.current = null; setDragging(null); };

  return <div className="settings">
    <p className="settings-intro">{t("settingsIntro")}</p>
    <section className="settings-card">
      <h3><Icon name="language"/>{t("language")}</h3>
      <p>{t("languageIntro")}</p>
      <div className="settings-row">
        <label htmlFor="settings-language">{t("languageLabel")}</label>
        <select id="settings-language" value={settings.language} disabled={busy} onChange={event => void save({language: event.target.value as Language})}>
          <option value="nl">Nederlands</option>
          <option value="en">English</option>
        </select>
      </div>
    </section>
    <section className="settings-card settings-order">
      <div className="settings-heading">
        <div><h3><Icon name="layers"/>{t("order")}</h3><p>{t("orderIntro")}</p></div>
        <div className="settings-actions">
          <button type="button" onClick={() => { setDraft(null); setMessage(""); }} disabled={!changed || busy}>{t("cancel")}</button>
          <button type="button" className="primary" onClick={() => void save({navOrder: order})} disabled={!changed || busy}>✓ {t("save")}</button>
        </div>
      </div>
      <ol ref={list} className="nav-order" onPointerMove={drag} onPointerUp={stopDrag} onPointerCancel={stopDrag}>
        {items.map((item, index) => <li key={item.id} data-nav-id={item.id} className={dragging === item.id ? "dragging" : undefined}>
          <button type="button" className="drag-handle" aria-label={`${item.label}: Alt+↑ ${t("moveUp")}, Alt+↓ ${t("moveDown")}`}
            onPointerDown={event => startDrag(event, item.id)} onPointerUp={stopDrag}
            onKeyDown={event => {
              if (!event.altKey || (event.key !== "ArrowUp" && event.key !== "ArrowDown")) return;
              event.preventDefault();
              const to = index + (event.key === "ArrowUp" ? -1 : 1);
              move(index, to);
              requestAnimationFrame(() => list.current?.querySelectorAll<HTMLButtonElement>(".drag-handle")[Math.max(0, Math.min(to, items.length - 1))]?.focus());
            }}>⠿</button>
          <Icon name={item.icon ?? "dashboard"}/><span>{item.label}</span>{item.children && <span className="chevron" aria-hidden="true">⌄</span>}
        </li>)}
      </ol>
      <div className="settings-footer">
        <button type="button" onClick={() => setDraft(defaults)} disabled={busy || order.join() === defaults.join()}>↺ {t("restore")}</button>
        <span>{t("hint")}</span>
      </div>
      <p role="status" className="settings-message">{message}</p>
    </section>
  </div>;
}
