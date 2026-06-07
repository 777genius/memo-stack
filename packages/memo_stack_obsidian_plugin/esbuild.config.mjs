import esbuild from "esbuild";

const production = process.env.NODE_ENV !== "development";
const watch = process.argv.includes("--watch");

const context = await esbuild.context({
  banner: {
    js: "/* Memo Stack Obsidian plugin */",
  },
  bundle: true,
  entryPoints: ["main.ts"],
  external: [
    "obsidian",
    "electron",
    "child_process",
    "node:child_process",
    "crypto",
    "node:crypto",
    "@codemirror/autocomplete",
    "@codemirror/collab",
    "@codemirror/commands",
    "@codemirror/language",
    "@codemirror/lint",
    "@codemirror/search",
    "@codemirror/state",
    "@codemirror/view",
    "@lezer/common",
    "@lezer/highlight",
    "@lezer/lr",
  ],
  format: "cjs",
  logLevel: "info",
  minify: production,
  outfile: "main.js",
  platform: "browser",
  sourcemap: production ? false : "inline",
  target: "es2018",
});

if (watch) {
  await context.watch();
  console.log("Watching Memo Stack Obsidian plugin...");
} else {
  await context.rebuild();
  await context.dispose();
}
