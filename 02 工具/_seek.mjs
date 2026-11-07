/* _seek.mjs — 逐镜 seek 体检：每个镜头 5 个时间点（0.05/0.25/0.5/0.75/0.98），零 pageerror 才算过
 * 用法：node "02 工具/_seek.mjs" "30 制作/2026-11-02_围一圈报数/web"
 */
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.dirname(HERE);
const REL = process.argv[2] || "30 制作/2026-11-02_围一圈报数/web";
const WEB = path.isAbsolute(REL) ? REL : path.join(ROOT, REL);
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";

const browser = await puppeteer.launch({
  executablePath: CHROME,
  headless: "shell",
  args: ["--headless=new", "--no-sandbox", "--force-device-scale-factor=1", "--disable-gpu"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1080, height: 1440, deviceScaleFactor: 1 });
const errs = [];
page.on("pageerror", (e) => errs.push("[pageerror] " + e.message));
page.on("console", (m) => {
  const t = m.text();
  if (/Failed to load resource/.test(t)) return;
  if (m.type() === "error") errs.push("[console] " + t);
});

await page.goto("file:///" + path.join(WEB, "index.html").replace(/\\/g, "/") + "?capture=1",
  { waitUntil: "load" });
await new Promise((r) => setTimeout(r, 800));

const shots = await page.evaluate(() =>
  window.TIMELINE.shots.map((s) => [s.id, s.scene, s.start, s.end]));

let n = 0, bad = 0;
for (const [id, scene, a, b] of shots) {
  for (const p of [0.05, 0.25, 0.5, 0.75, 0.98]) {
    const t = a + (b - a) * p;
    const before = errs.length;
    await page.evaluate((tt) => window.__seek(tt), t);
    await new Promise((r) => setTimeout(r, 30));
    n++;
    if (errs.length > before) { bad++; console.log("  ✗", id, t.toFixed(2)); }
  }
}
console.log(`seek ${n} 点 / 失败 ${bad} / 错误 ${errs.length}`);
errs.slice(0, 20).forEach((e) => console.log("  " + e));
await browser.close();
process.exit(errs.length ? 1 : 0);
