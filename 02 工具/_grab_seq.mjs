/* _grab_seq.mjs — 按 timeline.json 逐镜取中间帧，一期一次，用于人工复验
 * 用法：node _grab_seq.mjs --dir "30 制作/2026-11-02_围一圈报数/web" --out "99 归档/_复验截图/NO.18"
 *      node _grab_seq.mjs --dir ... --out ... --ratio 0.55
 * 说明：不动任何工程文件，只读 index.html + timeline.json，写 png。
 */
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";
import path from "node:path";

const arg = (k, d = "") => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : d; };
const DIR = path.resolve(arg("--dir"));
const OUT = path.resolve(arg("--out"));
const RATIO = Number(arg("--ratio", "0.55"));
const W = 1080, H = 1440;
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";

const tl = JSON.parse(fs.readFileSync(path.join(DIR, "timeline.json"), "utf8"));
const shots = tl.shots || [];
if (!shots.length) { console.error("timeline 里没有 shots"); process.exit(1); }
fs.mkdirSync(OUT, { recursive: true });

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "shell",
  args: ["--headless=new", "--no-sandbox", "--force-device-scale-factor=1", "--disable-gpu"],
});
const page = await browser.newPage();
await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });
const errs = [];
page.on("pageerror", e => errs.push(String(e)));
await page.goto("file:///" + path.join(DIR, "index.html").replace(/\\/g, "/") + "?capture=1", { waitUntil: "load" });
await new Promise(r => setTimeout(r, 700));

for (let i = 0; i < shots.length; i++) {
  const s = shots[i];
  const t = +(s.start + (s.end - s.start) * RATIO).toFixed(3);
  await page.evaluate(tt => window.__seek(tt), t);
  await new Promise(r => setTimeout(r, 240));
  const f = path.join(OUT, `${String(i).padStart(2, "0")}_${t.toFixed(1)}s.png`);
  await page.screenshot({ path: f });
  console.log(`→ ${path.basename(f)}  (${s.id || s.scene})`);
}
await browser.close();
if (errs.length) { console.log("[pageerror]", errs.slice(0, 5).join(" | ")); process.exit(2); }
console.log("[ok] " + shots.length + " 帧 -> " + OUT);
