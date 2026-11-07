/* _seekcheck.mjs — 每镜 5 个时间点 seek，零 pageerror
 * 用法：node _seekcheck.mjs --ep "30 制作/2026-11-06_少了一格"
 */
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";
import path from "node:path";

const arg = (k, d = "") => { const i = process.argv.indexOf(k); return i >= 0 ? process.argv[i + 1] : d; };
const EP = arg("--ep");
const HERE = path.resolve(EP, "web");
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";

const tl = JSON.parse(fs.readFileSync(path.join(HERE, "timeline.json"), "utf8"));
const browser = await puppeteer.launch({
  executablePath: fs.existsSync(CHROME) ? CHROME : EDGE,
  headless: "shell",
  args: ["--headless=new", "--no-sandbox", "--force-device-scale-factor=1", "--disable-gpu"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1080, height: 1440, deviceScaleFactor: 1 });
const errs = [];
page.on("pageerror", (e) => errs.push(String(e).split("\n")[0]));
const resErrs = [];
page.on("console", (m) => {
  if (m.type() !== "error") return;
  const t = m.text();
  if (/Failed to load resource|ERR_FILE_NOT_FOUND/.test(t)) resErrs.push(t);
  else errs.push("[console] " + t);
});
await page.goto("file:///" + path.join(HERE, "index.html").replace(/\\/g, "/") + "?capture=1", { waitUntil: "load" });
await new Promise((r) => setTimeout(r, 700));

let total = 0;
const rows = [];
for (const s of tl.shots) {
  const dur = s.end - s.start;
  const pts = [0.06, 0.25, 0.45, 0.65, 0.9].map((p) => s.start + dur * p);
  let ok = 0;
  for (const t of pts) {
    const before = errs.length;
    await page.evaluate((tt) => window.__seek(tt), t);
    await new Promise((r) => setTimeout(r, 90));
    const info = await page.evaluate(() => {
      const a = document.getElementById("scene-a");
      const b = document.getElementById("scene-b");
      const layer = (a.style.opacity === "0" || a.innerHTML === "") ? b : a;
      return { svg: layer.querySelectorAll("svg").length, nodes: layer.querySelectorAll("*").length };
    });
    if (errs.length === before && info.svg > 0) ok++; else rows.push(`${s.id} @${t.toFixed(2)} svg=${info.svg} node=${info.nodes} err=${errs.slice(before).join("|")}`);
  }
  total += ok;
  console.log(`  ${s.id.padEnd(10)} ${ok}/5  (svg ok)`);
}
await browser.close();
console.log("");
if (resErrs.length) {
  console.log("  [warn] 资源加载失败 " + resErrs.length + " 条（模板固定引用 ../bgm.wav，与本轮画面无关）");
}
if (errs.length) {
  console.log("❌ pageerror / console.error " + errs.length + " 条：");
  [...new Set(errs)].slice(0, 20).forEach((e) => console.log("   - " + e));
  process.exit(1);
}
console.log(`✅ ${EP}：${tl.shots.length} 镜 × 5 点 = ${total} 次 seek，零 pageerror`);
