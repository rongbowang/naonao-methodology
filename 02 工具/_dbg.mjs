import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import path from "node:path";
const WEB = path.resolve(process.argv[2]);
const browser = await puppeteer.launch({
  executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe",
  headless: "shell", args: ["--headless=new", "--no-sandbox", "--disable-gpu"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1080, height: 1440, deviceScaleFactor: 1 });
page.on("console", (m) => { if (!/Failed to load/.test(m.text())) console.log("LOG", m.type(), m.text()); });
page.on("pageerror", (e) => console.log("ERR", e.message, "\n", e.stack));
await page.goto("file:///" + path.join(WEB, "index.html").replace(/\\/g, "/") + "?capture=1", { waitUntil: "load" });
await new Promise((r) => setTimeout(r, 800));
const res = await page.evaluate(() => {
  const out = [];
  const TL = window.TIMELINE;
  const tmp = document.createElement("div");
  tmp.style.cssText = "position:absolute;left:0;top:0;width:1080px;height:1440px";
  document.getElementById("stage").appendChild(tmp);
  TL.shots.forEach((s) => {
    tmp.innerHTML = "";
    const box = K.div(tmp, null, { position: "absolute", inset: 0 });
    box.__SFX = [];
    const sc = Scenes[s.scene];
    let ctx = null, msg = "ok";
    try { ctx = sc.build(box, s); } catch (e) { msg = "build: " + e.message; }
    if (ctx) {
      ctx._box = box; ctx._shot = s;
      for (const p of [0.05, 0.25, 0.5, 0.75, 0.98]) {
        const tl = (s.end - s.start) * p;
        try { sc.update(ctx, tl, s); } catch (e) { msg = "update@" + tl.toFixed(2) + ": " + e.message + " || " + (e.stack||"").split("\n").slice(0,4).join(" / "); break; }
      }
    }
    out.push([s.id, msg]);
  });
  tmp.remove();
  return out;
});
res.forEach((r) => console.log(r[0], "->", r[1]));
await browser.close();
