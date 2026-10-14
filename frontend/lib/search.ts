export type SearchResult = {id: string; title: string; description: string} & (
  {kind: "app"; url: string} | {kind: "module"; route: string} | {kind: "dashboard"; route: "dashboard"; dashboardId: string}
);
export type SearchResponse = {results: SearchResult[]; warnings: string[]};
export type SearchEngine = {id: string; revision: number; name: string; urlTemplate: string};

export function externalSearchUrl(engine: Pick<SearchEngine, "name" | "urlTemplate">, query: string): string {
  const template = engine.urlTemplate;
  if (typeof query !== "string" || query.length > 200 || /[\u0000-\u001f]/.test(query) ||
      typeof engine.name !== "string" || !engine.name.trim() || engine.name.length > 80 ||
      typeof template !== "string" || template.length > 2048 || template.split("%s").length !== 2 || /[\s\\]/.test(template)) throw new TypeError("Ongeldige zoekmachine of zoekterm.");
  const authority = /^https?:\/\/([^/?#]+)/i.exec(template)?.[1];
  if (!authority || authority.includes("%s")) throw new TypeError("Gebruik een vast HTTP(S)-zoekadres.");
  const url = new URL(template.replace("%s", encodeURIComponent(query)));
  if (url.username || url.password || Array.from(url.searchParams.keys()).some(key => /token|api.?key|password|secret/i.test(key))) throw new TypeError("Gebruik een zoekadres zonder geheimen.");
  return url.href;
}

export async function searchEngineRequest(path = "", csrf = "", method = "GET", body?: unknown): Promise<{engines: SearchEngine[]}> {
  if (path !== "" && !/^\/[a-zA-Z0-9-]{1,64}$/.test(path)) throw new TypeError("Ongeldig zoekmachinepad.");
  const response = await fetch(`/api/search-engines${path}`, {method, cache: "no-store", headers: {"Content-Type": "application/json", ...(method === "GET" ? {} : {"X-CSRF-Token": csrf})}, body: body === undefined ? undefined : JSON.stringify(body)});
  if (!response.ok) {
    const result = await response.json().catch(() => ({}));
    throw new Error(typeof result.error === "string" ? result.error : "Zoekmachines zijn niet beschikbaar.");
  }
  const result = await response.json();
  if (method === "GET") {
    if (!Array.isArray(result.engines) || result.engines.length > 10) throw new TypeError("Ongeldige zoekmachinelijst.");
    for (const engine of result.engines) {
      if (!engine || typeof engine.id !== "string" || !/^[a-zA-Z0-9-]{1,64}$/.test(engine.id) || !Number.isInteger(engine.revision) || engine.revision < 1) throw new TypeError("Ongeldige zoekmachine.");
      externalSearchUrl(engine, "query");
    }
  }
  return result;
}

export function parseSearchResponse(value: unknown): SearchResponse {
  if (!value || typeof value !== "object" || !("results" in value) || !("warnings" in value) ||
      !Array.isArray(value.results) || value.results.length > 50 || !Array.isArray(value.warnings) || value.warnings.length > 10 ||
      value.warnings.some(warning => typeof warning !== "string" || warning.length > 300)) throw new TypeError("Ongeldige zoekresultaten.");
  for (const item of value.results) {
    if (!item || typeof item !== "object" || typeof item.id !== "string" || typeof item.title !== "string" || typeof item.description !== "string") throw new TypeError("Ongeldig zoekresultaat.");
    if (item.kind === "app") {
      const url = new URL(item.url);
      if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) throw new TypeError("Onveilig app-adres.");
    } else if (item.kind === "module" || item.kind === "dashboard") {
      if (typeof item.route !== "string" || !/^[a-z][a-z0-9-]*(?:\/[a-z][a-z0-9-]*)?$/.test(item.route)) throw new TypeError("Ongeldige route.");
      if (item.kind === "dashboard" && (item.route !== "dashboard" || typeof item.dashboardId !== "string" || !/^[a-zA-Z0-9-]{1,64}$/.test(item.dashboardId))) throw new TypeError("Ongeldig dashboard.");
    } else throw new TypeError("Onbekend zoekresultaat.");
  }
  return value as SearchResponse;
}

export async function searchRequest(query: string, signal?: AbortSignal): Promise<SearchResponse> {
  if (typeof query !== "string" || query.length > 200 || /[\u0000-\u001f]/.test(query)) throw new TypeError("Ongeldige zoekterm.");
  const response = await fetch(`/api/search?q=${encodeURIComponent(query)}`, {cache: "no-store", signal});
  if (!response.ok) throw new Error("Zoeken is tijdelijk niet beschikbaar. Probeer opnieuw.");
  return parseSearchResponse(await response.json());
}
