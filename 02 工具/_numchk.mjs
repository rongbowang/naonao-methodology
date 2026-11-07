/* _numchk.mjs — 读 scenes.js 在 build 时算好的编号排布自检结果
 * 用法：node "02 工具/_numchk.mjs" "30 制作/2026-11-02_围一圈报数/web"
 */
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import path from "node:path";
const WEB = path.resolve(process.argv[2]);
const b = await puppeteer.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: "shell", args: ["--headless=new", "--no-sandbox", "--disable-gpu"] });
const p = await b.newPage();
await p.setViewport({ width: 1080, height: 1440 });
await p.goto("file:///" + path.join(WEB, "index.html").replace(/\\/g, "/") + "?capture=1", { waitUntil: "load" });
await new Promise(r => setTimeout(r, 700));
const out = await p.evaluate(() => {
  const TL = window.TIMELINE, tmp = document.createElement("div");
  tmp.style.cssText = "position:absolute;left:0;top:0;width:1080px;height:1440px";
  document.getElementById("stage").appendChild(tmp);
  window.__NUMCHK = [];
  TL.shots.forEach((s) => {
    tmp.innerHTML = "";
    const box = K.div(tmp, null, { position: "absolute", inset: 0 });
    box.__SFX = [];
    Scenes[s.scene].build(box, s);
  });
  tmp.remove();
  return window.__NUMCHK;
});
let bad = 0;
out.forEach((r) => {
  if (!r.ok) bad++;
  console.log(`${r.ok ? "OK  " : "FAIL"} ${r.tag}  n=${r.n}  编号最小间距=${r.minNum}px  编号↔头=${r.minHead}px 编号↔身=${r.minBody}px 互压=${r.hitNum} 压头=${r.hitHead} 压身=${r.hitBody}`);
});
console.log(`---- ${out.length} 个环 / 不达标 ${bad}`);
await b.close();
process.exit(bad ? 1 : 0);
