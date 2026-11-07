// _dy_video.mjs —— 打开抖音视频页，抓 <video> 直链并下载
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const url = process.argv[2];
const out = process.argv[3] || "_dy.mp4";

const b = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--disable-blink-features=AutomationControlled",
         "--lang=zh-CN", "--autoplay-policy=no-user-gesture-required"],
  defaultViewport: { width: 430, height: 932, deviceScaleFactor: 1, isMobile: true, hasTouch: true },
});
const p = await b.newPage();
await p.setUserAgent("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1");
await p.evaluateOnNewDocument(() => Object.defineProperty(navigator, "webdriver", { get: () => undefined }));

const media = [];
p.on("response", (res) => {
  const u = res.url();
  const ct = (res.headers()["content-type"] || "");
  if (ct.includes("video") || /\.mp4|douyinvod|bytevcloud/.test(u)) media.push(u);
});

await p.goto(url, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(e => console.log("goto", e.message));
await new Promise(r => setTimeout(r, 7000));

const info = await p.evaluate(() => {
  const v = document.querySelector("video");
  return {
    hasVideo: !!v,
    src: v ? (v.currentSrc || v.src || (v.querySelector("source") || {}).src || "") : "",
    dur: v ? v.duration : 0,
    w: v ? v.videoWidth : 0,
    h: v ? v.videoHeight : 0,
    posters: Array.from(document.querySelectorAll("video[poster], img")).map(e => e.poster || e.src).filter(Boolean).slice(0, 6),
    body: (document.body.innerText || "").slice(0, 600),
  };
});
console.log(JSON.stringify({ ...info, body: undefined, mediaCount: media.length }, null, 1));
console.log("-- 前 3 条 media --");
media.slice(0, 3).forEach(u => console.log(u.slice(0, 200)));
fs.writeFileSync("_dy_media.json", JSON.stringify({ info, media }, null, 1), "utf-8");
await b.close();
