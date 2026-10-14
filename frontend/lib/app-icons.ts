/** Use only the destination origin, without paths, credentials or queries. */
export function websiteFavicon(url: string): string | null {
  try { const value = new URL(url); return ["http:", "https:"].includes(value.protocol) && !value.username && !value.password ? `${value.origin}/favicon.ico` : null; } catch { return null; }
}

/** Normalize user images to a small PNG before storing them with the personal tile. */
export async function uploadDashboardIcon(file: File): Promise<string> {
  if (file.type !== "image/png" || !file.size || file.size > 2 * 1024 * 1024) throw new Error("Kies een PNG van maximaal 2 MB.");
  const image = await createImageBitmap(file);
  try {
    if (!image.width || !image.height || image.width > 4096 || image.height > 4096) throw new Error("Afbeelding te groot: maximaal 4096 × 4096 pixels.");
    const canvas = document.createElement("canvas"); canvas.width = 64; canvas.height = 64;
    const context = canvas.getContext("2d"); if (!context) throw new Error("Afbeelding verwerken mislukt.");
    const scale = Math.min(64 / image.width, 64 / image.height);
    const width = image.width * scale, height = image.height * scale;
    context.drawImage(image, (64 - width) / 2, (64 - height) / 2, width, height);
    return canvas.toDataURL("image/png");
  } finally { image.close(); }
}
