import { mkdir, readFile } from "node:fs/promises";
import { resolve, join } from "node:path";
import { chromium } from "playwright";
import { createRenderer, presets } from "@maurogoncalo/clickclick";

if (process.argv.length !== 4) {
  throw new Error("Usage: node render.mjs INPUT_JSON OUTPUT_DIR");
}

const input = JSON.parse(await readFile(resolve(process.argv[2]), "utf8"));
const output = resolve(process.argv[3]);
await mkdir(output, { recursive: true });

const tasks = [
  {
    name: "cover",
    options: presets.gradient({
      title: input.headline,
      subtitle: input.hook,
      label: "中文区热点 · XHotLab",
      textColor: "#ffffff",
    }),
  },
  {
    name: "context",
    options: presets.solid({
      title: input.context_title,
      subtitle: input.explanation,
      label: input.source,
      backgroundColor: "#fff8ef",
      accentColor: "#e5673f",
      textColor: "#242c44",
    }),
  },
  {
    name: "discussion",
    options: presets.gradient({
      title: input.question,
      subtitle: input.takeaway,
      label: "互动话题 · XHotLab",
      textColor: "#ffffff",
    }),
  },
];

const browser = await chromium.launch({ channel: "msedge", headless: true });
const renderer = await createRenderer({ browser });
try {
  for (const task of tasks) {
    const filename = join(output, task.name + ".png");
    await renderer.render({
      ...task.options,
      viewport: { width: 900, height: 1200 },
      document: {
        ...task.options.document,
        css: task.options.document.css + [
          "body,main{width:900px!important;height:1200px!important;}",
          "main{padding:110px 83px!important;align-items:center!important;}",
          "section{gap:48px!important;}",
          "h1{max-height:560px!important;line-height:1.18!important;}",
          "p{max-height:420px!important;line-height:1.5!important;}",
          ".accent{left:83px!important;top:84px!important;}",
        ].join("\n"),
      },
      output: { path: filename, format: "png" },
    });
    console.log(filename);
  }
} finally {
  await renderer.close();
  await browser.close();
}
