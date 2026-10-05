import fs from "node:fs";
import path from "node:path";

const root = path.resolve("node_modules");
const names = new Set(["license", "license.txt", "license.md", "licence", "licence.txt", "copying", "copying.txt", "notice", "notice.txt"]);
const entries = [];
function collect(directory) {
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const target = path.join(directory, entry.name);
    if (entry.isDirectory()) collect(target);
    else if (entry.isFile() && (names.has(entry.name.toLowerCase()) || entry.name.toLowerCase().startsWith("license-"))) {
      const relative = path.relative(root, target).replaceAll(path.sep, "/");
      entries.push([relative, fs.readFileSync(target, "utf8")]);
    }
  }
}
collect(root);
entries.sort((a, b) => a[0].localeCompare(b[0]));
const content = "Third-party license texts from the installed frontend dependency tree.\nPinned dependencies: frontend/package-lock.json. Build-only dependencies may also be listed.\n\n" + entries.map(([name, text]) => `===== ${name} =====\n${text}`).join("\n\n");
fs.writeFileSync("out/THIRD-PARTY-LICENSES.txt", content);
console.log(`Included ${entries.length} third-party license texts in the static export.`);
