export type Language = "nl" | "en";
const text = {
  nl: {
    settings: "Instellingen", settingsIntro: "Beheer je persoonlijke voorkeuren",
    language: "Interfacetaal", languageIntro: "Kies de taal van ControlDeck.", languageLabel: "Taal",
    order: "Menuvolgorde", orderIntro: "Bepaal de volgorde van de hoofdtabbladen. Groepen zoals Proxmox en Admin verplaatsen als geheel; hun onderdelen behouden de standaardvolgorde.",
    cancel: "Annuleren", save: "Opslaan", saved: "Opgeslagen", restore: "Standaard herstellen", hint: "Sleep om te ordenen · Op touch eerst lang drukken · Toetsenbord: Alt+pijl",
    saveFailed: "Opslaan is mislukt. Probeer het opnieuw.", moveUp: "omhoog", moveDown: "omlaag", logout: "Uitloggen",
  },
  en: {
    settings: "Settings", settingsIntro: "Manage your personal preferences",
    language: "Interface language", languageIntro: "Choose the language used by ControlDeck.", languageLabel: "Language",
    order: "Navigation order", orderIntro: "Personalize the order of the top-level tabs. Grouped tabs such as Proxmox and Admin move as a single unit; their internal items keep their default order.",
    cancel: "Cancel", save: "Save", saved: "Saved", restore: "Restore default", hint: "Drag to reorder · On touch, long-press first · Keyboard: Alt+arrow",
    saveFailed: "Saving failed. Please try again.", moveUp: "up", moveDown: "down", logout: "Log out",
  },
} as const;
export type TextKey = keyof typeof text.nl;
export function translate(language: string | undefined, key: TextKey): string {
  return (text[language as Language] ?? text.nl)[key];
}
