// CalVer builds (2026.10.05.31) and the historical semver releases (0.1.0–0.4.0) both have a release tag v<version>.
const RELEASED = /^(\d{4}\.\d{2}\.\d{2}\.[1-9]\d*|0\.\d+\.\d+)$/;
/** Release notes for the running version on GitHub: the exact release for a released version, otherwise the release list. */
export function releaseNotesUrl(repositoryUrl: string, version: string | undefined): string | null {
  let url: URL;
  try { url = new URL(repositoryUrl); } catch { return null; }
  const path = url.pathname.replace(/\/+$/, "");
  if (url.protocol !== "https:" || url.hostname !== "github.com" || !/^\/[\w.-]+\/[\w.-]+$/.test(path)) return null;
  const base = `https://github.com${path}/releases`;
  return version && RELEASED.test(version) ? `${base}/tag/v${version}` : base;
}
