/** Files (Nextcloud) client helpers. The server checks every path again; these only shape requests and display. */
export type FileItem = {name: string; type: "folder" | "file"; size: number | null; modified: number | null};
export type FilesConnection = {linked: boolean; loginName: string | null; server: string};
export const MAX_UPLOAD = 10 * 1024 ** 3;

export class FilesRequestError extends Error {
  readonly status: number;
  readonly relink: boolean;
  constructor(message: string, status: number, relink = false) { super(message); this.status = status; this.relink = relink; }
}

/** Normalised relative path; refuses traversal and control characters like the server. */
export function filesPath(value: string): string {
  if (typeof value !== "string" || value.length > 1024 || /[\u0000-\u001f\u007f\\]/.test(value)) throw new RangeError("Ongeldig pad.");
  const parts = value.split("/").filter(Boolean);
  if (parts.some(part => part === "." || part === ".." || part.length > 255)) throw new RangeError("Ongeldig pad.");
  return parts.join("/");
}

export function joinPath(folder: string, name: string): string {
  if (!name || name.includes("/")) throw new RangeError("Gebruik een naam zonder schuine streep.");
  return filesPath(folder ? `${folder}/${name}` : name);
}

export function parentPath(path: string): string {
  const parts = filesPath(path).split("/").filter(Boolean);
  return parts.slice(0, -1).join("/");
}

/** Breadcrumb segments with the path up to each segment; the first entry is the root. */
export function breadcrumbs(path: string): {name: string; path: string}[] {
  const parts = filesPath(path).split("/").filter(Boolean);
  return [{name: "Bestanden", path: ""}, ...parts.map((name, index) => ({name, path: parts.slice(0, index + 1).join("/")}))];
}

export function formatSize(bytes: number | null): string {
  if (bytes === null || !Number.isFinite(bytes) || bytes < 0) return "";
  const units = ["B", "KB", "MB", "GB", "TB"];
  let value = bytes, unit = 0;
  while (value >= 1024 && unit < units.length - 1) { value /= 1024; unit++; }
  return `${unit === 0 ? value : value.toFixed(value < 10 ? 1 : 0)} ${units[unit]}`.replace(".", ",");
}

/** Byte ranges for a chunked upload; a single small request when the file fits in one chunk. */
export function uploadPlan(size: number, chunkSize: number): {index: number; start: number; end: number}[] {
  if (!Number.isInteger(size) || size < 0 || size > MAX_UPLOAD) throw new RangeError("Een bestand mag hooguit 10 GB zijn.");
  if (!Number.isInteger(chunkSize) || chunkSize < 1) throw new RangeError("Ongeldige deelgrootte.");
  const plan = [];
  for (let start = 0, index = 1; start < size; start += chunkSize, index++) plan.push({index, start, end: Math.min(size, start + chunkSize)});
  return plan;
}

export function downloadUrl(path: string): string {
  return `/api/files/download?path=${encodeURIComponent(filesPath(path))}`;
}

export async function filesRequest<T>(route: string, csrf = "", method = "GET", body?: BodyInit | object, signal?: AbortSignal): Promise<T> {
  if (!/^\/[a-z/0-9-]*(\?[^#]*)?$/.test(route)) throw new TypeError("Ongeldige Files-route.");
  const raw = body instanceof Blob || body === undefined;
  const response = await fetch(`/api/files${route}`, {
    method, cache: "no-store", signal,
    headers: {...(method === "GET" ? {} : {"X-CSRF-Token": csrf}), ...(raw ? {} : {"Content-Type": "application/json"})},
    body: raw ? body as BodyInit | undefined : JSON.stringify(body),
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new FilesRequestError(typeof result.error === "string" ? result.error : `Files is niet beschikbaar (status ${response.status}).`, response.status, result.relink === true);
  return result as T;
}
