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
  const box = K.div(tmp, null, { position: "absolute", inset: 0 });
  box.__SFX = [];
  const ctx = Scenes[TL.shots[0].scene].build(box, TL.shots[0]);
  const rows = ctx.ring.map((o, i) => {
    let dmin = 1e9, jmin = -1;
    ctx.ring.forEach((b2, j) => { if (i !== j) { const d = Math.hypot(o.tagX - b2.tagX, o.tagY - b2.tagY); if (d < dmin) { dmin = d; jmin = j; } } });
    return [i + 1, +o.x.toFixed(1), +o.y.toFixed(1), +o.tagX.toFixed(1), +o.tagY.toFixed(1), +dmin.toFixed(1), jmin + 1];
  });
  tmp.remove();
  return rows;
});
console.log("号  x     y     编号x   编号y   最近邻距 最近邻号");
out.forEach(r => console.log(r.join("  ")));
await b.close();
