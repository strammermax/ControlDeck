/** Build on CI; serve the exported files from Flask at runtime. */
const config = { output: "export", trailingSlash: true, images: { unoptimized: true } };
export default config;
