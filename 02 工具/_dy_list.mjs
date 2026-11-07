// _dy_list.mjs —— 主页取 video id，再逐个访问详情页抓标题
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const USER = process.argv[2];
const b = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--disable-blink-features=AutomationControlled",
         "--lang=zh-CN", "--window-size=430,932"],
  defaultViewport: { width: 430, height: 932, deviceScaleFactor: 1, isMobile: true, hasTouch: true },
});
const p = await b.newPage();
await p.setUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1");
await p.evaluateOnNewDocument(() => Object.defineProperty(navigator, "webdriver", { get: () => undefined }));

await p.goto(USER, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(e => console.log("goto", e.message));
await new Promise(r => setTimeout(r, 6000));
const ids = new Set();
for (let i = 0; i < 12; i++) {
  const arr = await p.evaluate(() => Array.from(document.querySelectorAll('a[href*="/video/"]'))
    .map(a => (a.getAttribute("href").match(/video\/(\d+)/) || [])[1]).filter(Boolean)).catch(() => []);
  arr.forEach(x => ids.add(x));
  await p.evaluate(() => window.scrollBy(0, 1500)).catch(() => {});
  await new Promise(r => setTimeout(r, 1500));
}
console.log("视频 id:", ids.size);
await b.close();

const all = [];
const b2 = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--disable-blink-features=AutomationControlled", "--lang=zh-CN"],
  defaultViewport: { width: 430, height: 932, deviceScaleFactor: 1, isMobile: true },
});
const q = await b2.newPage();
await q.setUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1");
await q.evaluateOnNewDocument(() => Object.defineProperty(navigator, "webdriver", { get: () => undefined }));
for (const id of Array.from(ids).slice(0, 22)) {
  await q.goto("https://www.douyin.com/video/" + id, { waitUntil: "domcontentloaded", timeout: 45000 }).catch(() => {});
  await new Promise(r => setTimeout(r, 3500));
  const t = await q.title();
  const clean = t.replace(/\s*-\s*抖音\s*$/, "").replace(/\s+/g, " ").trim();
  all.push({ id, title: clean });
  console.log(String(all.length).padStart(2, "0"), clean.slice(0, 100));
}
fs.writeFileSync("_dy_list.json", JSON.stringify(all, null, 1), "utf-8");
await b2.close();
