// _dy_grab.mjs —— 用真实 Chrome 打开抖音分享页，抓文案 / 数据 / 截图
// 用法： node _dy_grab.mjs <url> <outPrefix>
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";
import path from "node:path";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const url = process.argv[2];
const out = process.argv[3] || "_dy";
if (!url) { console.error("need url"); process.exit(1); }

const b = await puppeteer.launch({
  executablePath: CHROME,
  headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--disable-blink-features=AutomationControlled",
         "--lang=zh-CN", "--window-size=430,932"],
  defaultViewport: { width: 430, height: 932, deviceScaleFactor: 2, isMobile: true, hasTouch: true },
});
const p = await b.newPage();
await p.setUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1");
await p.evaluateOnNewDocument(() => {
  Object.defineProperty(navigator, "webdriver", { get: () => undefined });
});

const seen = [];
p.on("response", async (res) => {
  const u = res.url();
  if (/aweme\/detail|aweme\/post|iteminfo|aweme\/v1\/web/.test(u)) {
    seen.push(u.slice(0, 160));
  }
});

await p.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(e => console.log("goto:", e.message));
await new Promise(r => setTimeout(r, 6000));

// 滚一下，触发异步渲染
await p.evaluate(() => window.scrollBy(0, 200)).catch(() => {});
await new Promise(r => setTimeout(r, 3000));

const info = await p.evaluate(() => {
  const t = (sel) => { const e = document.querySelector(sel); return e ? e.innerText.trim() : ""; };
  const pick = (sels) => { for (const s of sels) { const v = t(s); if (v) return v; } return ""; };
  return {
    title: document.title,
    desc: pick(['[data-e2e="video-desc"]', '[data-e2e="detail-video-desc"]', "h1", ".video-info-detail"]),
    author: pick(['[data-e2e="video-author-name"]', '[data-e2e="user-name"]', ".author-name"]),
    stats: pick(['[data-e2e="video-like-count"]', '[data-e2e="like-count"]']),
    bodyText: (document.body.innerText || "").slice(0, 3000),
    imgCount: document.images.length,
    imgs: Array.from(document.images).map(i => ({ src: i.currentSrc || i.src, w: i.naturalWidth, h: i.naturalHeight }))
      .filter(x => x.w > 60).slice(0, 40),
  };
});

fs.writeFileSync(out + ".json", JSON.stringify({ url, info, api: seen }, null, 1), "utf-8");
await p.screenshot({ path: out + ".png" }).catch(() => {});
console.log("title:", info.title);
console.log("author:", info.author, "| like:", info.stats);
console.log("desc:", info.desc.slice(0, 300));
console.log("imgs:", info.imgs.length, "api hits:", seen.length);
console.log("--- body ---");
console.log(info.bodyText.slice(0, 1200));
await b.close();
