// _apodfg_list.mjs —— 抓 Apodfg 主页全部作品（id/标题/时长/点赞），用于系列横向拆解
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";

const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36";

const b = await puppeteer.launch({
  executablePath: CHROME, headless: "new",
  args: ["--no-sandbox", "--disable-gpu", "--disable-blink-features=AutomationControlled", "--lang=zh-CN"],
  defaultViewport: { width: 1440, height: 1000 },
});
const p = await b.newPage();
await p.setUserAgent(UA);
await p.evaluateOnNewDocument(() => Object.defineProperty(navigator, "webdriver", { get: () => undefined }));

// 1) 先拿 sec_uid
await p.goto("https://www.douyin.com/video/7697253017464098067", { waitUntil: "domcontentloaded", timeout: 60000 }).catch(e => console.log("goto1", e.message));
await new Promise(r => setTimeout(r, 6000));
const sec = await p.evaluate(() => {
  const a = Array.from(document.querySelectorAll('a[href*="/user/"]')).map(x => x.getAttribute("href"));
  const m = a.map(h => (h.match(/user\/([\w\-]+)/) || [])[1]).filter(Boolean);
  return m[0] || null;
});
console.log("sec_uid =", sec);
if (!sec) { await b.close(); process.exit(1); }

// 2) 主页滚动收集卡片
await p.goto("https://www.douyin.com/user/" + sec, { waitUntil: "domcontentloaded", timeout: 60000 }).catch(e => console.log("goto2", e.message));
await new Promise(r => setTimeout(r, 7000));
const dump = async () => p.evaluate(() => {
  const out = [];
  document.querySelectorAll('a[href*="/video/"]').forEach(a => {
    const id = (a.getAttribute("href").match(/video\/(\d+)/) || [])[1];
    if (!id) return;
    const box = a.closest("li") || a.parentElement;
    const txt = (box ? box.innerText : a.innerText || "").replace(/\s+/g, " ").trim();
    out.push({ id, txt });
  });
  return out;
});
let all = [];
for (let i = 0; i < 14; i++) {
  const arr = await dump().catch(() => []);
  all = all.concat(arr);
  await p.evaluate(() => window.scrollBy(0, 2000)).catch(() => {});
  await new Promise(r => setTimeout(r, 1800));
}
const map = new Map();
for (const x of all) {
  const prev = map.get(x.id);
  if (!prev || (x.txt || "").length > (prev.txt || "").length) map.set(x.id, x);
}
const list = Array.from(map.values());
console.log("卡片数:", list.length);
fs.writeFileSync("_apodfg_cards.json", JSON.stringify(list, null, 1), "utf-8");
console.log(list.slice(0, 40).map(x => x.id + " | " + x.txt.slice(0, 60)).join("\n"));
await b.close();
