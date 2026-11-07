import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const puppeteer = require("puppeteer-core");
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const PAGE = path.join(HERE, "窗口提示词_2026-11.html");
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";
const EDGE = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
const browser = await puppeteer.launch({
  executablePath: fs.existsSync(CHROME) ? CHROME : EDGE,
  headless: "shell",
  args: ["--headless=new", "--no-sandbox", "--force-device-scale-factor=1", "--disable-gpu"],
});
const page = await browser.newPage();
await page.setViewport({ width: 1280, height: 900, deviceScaleFactor: 1 });
const errs = [];
page.on("pageerror", e => errs.push(String(e)));
await page.goto("file:///" + PAGE.replace(/\\/g, "/"), { waitUntil: "networkidle0" });

const tas = await page.$$eval("textarea", els => els.map(e => ({
  id: e.id, len: e.value.length, head: e.value.slice(0, 20)
})));
console.log("TEXTAREA", tas.length, "EMPTY", tas.filter(t => !t.len).length);
tas.forEach(t => console.log("  ", t.id, t.len, t.head.replace(/\n/g, " ")));
console.log("BUTTONS", await page.$$eval("button.cp", b => b.length));

await page.click("button.cp");
await new Promise(r => setTimeout(r, 250));
console.log("BUTTON_1_AFTER_CLICK", await page.$eval("button.cp", b => b.textContent));

console.log("JS_ERRORS", errs.length, errs.slice(0, 3).join(" | "));
await page.screenshot({ path: path.join(HERE, "_首屏.png") });
console.log("SCREENSHOT _首屏.png");
await browser.close();
