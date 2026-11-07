// _dy_user.mjs —— 滚动抓抖音主页作品列表（标题 + 赞数）
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const url = process.argv[2];
const b = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--disable-blink-features=AutomationControlled",
         "--lang=zh-CN", "--window-size=430,932"],
  defaultViewport: { width: 430, height: 932, deviceScaleFactor: 1, isMobile: true, hasTouch: true },
});
const p = await b.newPage();
await p.setUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1");
await p.evaluateOnNewDocument(() => Object.defineProperty(navigator, "webdriver", { get: () => undefined }));
await p.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(e => console.log("goto", e.message));
await new Promise(r => setTimeout(r, 6000));

const collect = () => p.evaluate(() => {
  const out = [];
  const nodes = document.querySelectorAll('a[href*="/video/"], li, div[data-e2e]');
  // 网页版作品卡通常带 alt（等于标题）的 img
  document.querySelectorAll("img[alt]").forEach(im => {
    const t = (im.alt || "").trim();
    if (t.length > 6) out.push({ title: t.replace(/\s+/g, " "), src: im.src });
  });
  return out;
});

const seen = new Map();
for (let i = 0; i < 14; i++) {
  const arr = await collect().catch(() => []);
  arr.forEach(x => { if (!seen.has(x.title)) seen.set(x.title, x.src); });
  await p.evaluate(() => window.scrollBy(0, 1400)).catch(() => {});
  await new Promise(r => setTimeout(r, 1600));
}

const list = Array.from(seen.entries()).map(([title, src]) => ({ title, src }));
fs.writeFileSync("_dy_works.json", JSON.stringify(list, null, 1), "utf-8");
console.log("抓到", list.length, "条");
list.forEach((x, i) => console.log(String(i + 1).padStart(2, "0"), x.title.slice(0, 110)));
await b.close();
