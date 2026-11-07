# -*- coding: utf-8 -*-
"""_canvas.py —— 把一期的渲染工程切到任意画布尺寸（默认横屏 4:3 = 1440×1080）。

★ 2026-11-02 起因：用户要求 11-02 及以后的期改横屏 4:3，「更好布局画面」，
  并且主人公要放大。竖屏 1080×1440 的高度被砍到 1080，构图必须重排，
  但**引擎不该再写死任何尺寸** —— 所以先把尺寸变成数据，再改画面。

做法（全部幂等，重复跑不会叠加）：
  1. 写 size.json        {"width":1440,"height":1080}
  2. gen_timeline.py     读 size.json -> timeline.json 的 width/height
  3. js/kit.js           注入 K.VW / K.VH / K.CX / K.CY / K.SAFE_BOT（来源是 TIMELINE）
  4. js/lib.js           stage2 / bg / 扫光 / 主光 / 呼吸膜 / outroStd 全部改用 K.*
  5. js/assets.js        grain / vignette / snow 的全屏 rect 改用 K.*
  6. js/engine.js        舞台尺寸、缩放适配、字幕排版、音效预扫描的离屏容器
  7. capture / _check / _gcheck / _overlap / _shot 的 viewport 从 timeline.json 读

用法：
    python "02 工具/_canvas.py" NO.23            # 该期转横屏
    python "02 工具/_canvas.py" --all            # 五期一起
    python "02 工具/_canvas.py" NO.23 --w 1080 --h 1440   # 转回竖屏
"""
import os, sys, json, io, re

WORK = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROD = os.path.join(WORK, "30 制作")
EPS = ["NO.19_地球加长一米", "NO.20_住满的旅馆", "NO.21_两扇门",
       "NO.22_少了一格", "NO.23_蒙眼分硬币"]


# ---------- 读写（保留换行风格，幂等替换） ----------
def rd(p):
    with io.open(p, "r", encoding="utf-8", newline="") as f:
        raw = f.read()
    crlf = "\r\n" in raw
    return raw.replace("\r\n", "\n"), crlf


def wr(p, text, crlf):
    if crlf:
        text = text.replace("\n", "\r\n")
    with io.open(p, "w", encoding="utf-8", newline="") as f:
        f.write(text)


class Patcher:
    def __init__(self, path):
        self.path = path
        self.text, self.crlf = rd(path)
        self.log = []

    def sub(self, old, new, name="", idem=None):
        # idem：幂等哨兵。文本里已经有它 = 这一步做过了，直接跳过
        # （★ 教训：锚点本身会出现在替换结果里时，重复跑会插第二遍，
        #   `const __CV` 重复声明直接 SyntaxError 白屏。）
        if idem and idem in self.text:
            self.log.append("  = 已就位 %s" % (name or old[:40]))
            return
        n = self.text.count(old)
        if n == 0:
            if new in self.text:
                self.log.append("  = 已就位 %s" % (name or old[:40]))
                return
            raise SystemExit("✗ 找不到锚点 [%s] %s\n  %r" % (os.path.basename(self.path), name, old[:110]))
        if n > 1 and name != "*":
            raise SystemExit("✗ 锚点不唯一（%d 处）%s\n  %r" % (n, name, old[:110]))
        self.text = self.text.replace(old, new) if name == "*" else self.text.replace(old, new, 1)
        self.log.append("  ✓ %s" % (name or old[:40]))

    def save(self):
        wr(self.path, self.text, self.crlf)
        for l in self.log:
            print(l)


# ---------- 各文件 ----------
def patch_kit(web):
    p = Patcher(os.path.join(web, "js", "kit.js"))
    p.sub("""const K = {""",
          """// ============ 画布尺寸（★ 2026-11-02 参数化）============
// 唯一来源是 timeline.json 的 width/height（由 gen_timeline.py 从 size.json 写入）。
// 竖屏 3:4 = 1080×1440；横屏 4:3 = 1440×1080。
// 全屏层 / 居中点 / 字幕安全线一律走 K.VW / K.VH / K.CX / K.CY —— 别再写死数字。
// ⚠ 只挂在 K 上，不建全局 const：scenes.js 顶层已有 CX/CY 之类的同名常量，
//   在全局再声明一个会直接 SyntaxError 白屏。
const __CV = (typeof window !== "undefined" && window.TIMELINE) || {};

const K = {
  VW: __CV.width || 1080,
  VH: __CV.height || 1440,
  CX: (__CV.width || 1080) / 2,
  CY: (__CV.height || 1440) / 2,""", "kit: 注入画布常量", idem="const __CV =")
    p.sub("  SAFE_BOT: 1104,",
          "  SAFE_BOT: (__CV.height || 1440) >= 1400 ? 1104 : 760,", "kit: SAFE_BOT 随尺寸", idem="__CV.height || 1440) >= 1400")
    p.save()


def patch_lib(web):
    p = Patcher(os.path.join(web, "js", "lib.js"))
    # bg()
    p.sub('K.sp(svg, "rect", { x: 0, y: 0, width: 1080, height: 1440, fill: `url(#${id})` });',
          'K.sp(svg, "rect", { x: 0, y: 0, width: K.VW, height: K.VH, fill: `url(#${id})` });',
          "lib: bg 全屏渐变")
    # stage2 svg
    p.sub('const svg = K.svg(box, 1080, 1440, { position: "absolute", inset: 0 });',
          'const svg = K.svg(box, K.VW, K.VH, { position: "absolute", inset: 0 });',
          "lib: stage2 svg 尺寸")
    # 环境呼吸柔光
    p.sub("                     540, 690, 560, LT ? 0.055 : 0.10);",
          "                     K.CX, K.VH * 0.48, K.VW * 0.52, LT ? 0.055 : 0.10);",
          "lib: 呼吸柔光位置")
    # 主扫光
    p.sub('    const sw = K.sp(svg, "rect", { x: -760, y: 0, width: 760, height: 1440,',
          '    const swW = Math.round(K.VW * 0.70);\n'
          '    const sw = K.sp(svg, "rect", { x: -swW, y: 0, width: swW, height: K.VH,',
          "lib: 主扫光宽度")
    p.sub("    svg.__sweep = sw;", "    svg.__sweep = sw; svg.__swW = swW;", "lib: 记下扫光宽度")
    # 反向扫光
    p.sub('    svg.__sweep2 = K.sp(svg, "rect", { x: 1620, y: 0, width: 900, height: 1440,',
          '    const sw2W = Math.round(K.VW * 0.83);\n'
          '    svg.__sweep2 = K.sp(svg, "rect", { x: K.VW + 540, y: 0, width: sw2W, height: K.VH,',
          "lib: 反向扫光宽度")
    p.sub('      fill: `url(#${id}_swg2)` });',
          '      fill: `url(#${id}_swg2)` });\n    svg.__sw2W = sw2W;',
          "lib: 记下反向扫光宽度")
    # 游走主光
    p.sub('    const kl = glow(svg, id + "_key", LT ? "#A9C6DF" : "#8FC6FF", 540, 690, 380,',
          '    const kl = glow(svg, id + "_key", LT ? "#A9C6DF" : "#8FC6FF", K.CX, K.VH * 0.48, 380,',
          "lib: 游走主光位置")
    # 呼吸膜
    p.sub('    svg.__veil = K.sp(svg, "rect", { x: 0, y: 0, width: 1080, height: 1440,',
          '    svg.__veil = K.sp(svg, "rect", { x: 0, y: 0, width: K.VW, height: K.VH,',
          "lib: 呼吸膜尺寸")
    # 扫光运动范围（bgmotion / cam 的两个分支共 3 处，先处理 ctx.svg 那两处）
    p.sub('ctx.svg.__sweep.setAttribute("x", (-760 + q * 1840).toFixed(0));',
          'ctx.svg.__sweep.setAttribute("x", (-(ctx.svg.__swW || 760) + q * (K.VW + (ctx.svg.__swW || 760))).toFixed(0));',
          "*")
    p.sub('svg.__sweep.setAttribute("x", (-760 + q * 1840).toFixed(0));',
          'svg.__sweep.setAttribute("x", (-(svg.__swW || 760) + q * (K.VW + (svg.__swW || 760))).toFixed(0));',
          "lib: 主扫光行程")
    p.sub('svg.__sweep2.setAttribute("x", (1620 - q2 * 2520).toFixed(0));',
          'svg.__sweep2.setAttribute("x", ((K.VW + 540) - q2 * (K.VW + 540 + (svg.__sw2W || 900))).toFixed(0));',
          "*")
    # critter 默认居中
    p.sub("const cx = opt.cx === undefined ? 540 : opt.cx;",
          "const cx = opt.cx === undefined ? K.CX : opt.cx;", "lib: critter 默认居中")
    # 片尾：横屏改左右两栏
    p.sub("""      const LT = !!window.LIGHT;
      const svg = stage2(box, "bgO", LT ? "#FFFFFF" : "#0E1A2A", LT ? "#E8F0F8" : "#050C16");
      glow(svg, "gO1", LT ? "#9CC0DC" : GOLD, 540, 780, 330, LT ? 0.06 : 0.13);

      // 期号徽章
      const badge = K.sp(svg, "g", {});
      K.sp(badge, "circle", { cx: 540, cy: 300, r: 92,
        fill: LT ? "#FFFFFF" : "#0C1B2E", stroke: GOLD, "stroke-width": 5 });
      K.sp(badge, "circle", { cx: 540, cy: 300, r: 74, fill: "none",
        stroke: GOLD, "stroke-width": 2, opacity: .55 });
      const bt = K.sp(badge, "text", { x: 540, y: 316, fill: GOLD, "font-size": 38,
        "font-weight": 900, "text-anchor": "middle" });
      bt.textContent = no;

      // 两句胶囊：避开字幕安全区（≤1104）
      const done = chip(box, "装进脑子", GOLD, 540, 1032, 30);
      const brand = chip(box, "关注 脑脑不老佬", GOLD, 540, 946, 34);

      // ★ 账号符号：脑子。没它就等于没片尾。
      const brain = brainImg(svg, 540, 616, 344);

      return { svg, badge, done, brand, brain,""",
          """      const LT = !!window.LIGHT;
      const svg = stage2(box, "bgO", LT ? "#FFFFFF" : "#0E1A2A", LT ? "#E8F0F8" : "#050C16");
      // 竖屏：脑子居中、徽章在上；横屏 4:3：脑子占左半、徽章与胶囊组成右栏
      const wide = K.VH < 1400;
      const bxc = wide ? K.CX - 330 : K.CX;      // 脑子中心
      const byc = wide ? K.VH * 0.50 : 616;
      const bwd = wide ? 360 : 344;
      const bxc2 = wide ? K.CX + 310 : K.CX;     // 徽章 / 胶囊那一列
      const byc2 = wide ? 400 : 300;
      const chipY1 = wide ? 690 : 946;           // 「关注 脑脑不老佬」
      const chipY2 = wide ? 580 : 1032;          // 「装进脑子」
      glow(svg, "gO1", LT ? "#9CC0DC" : GOLD, bxc, byc, wide ? 300 : 330, LT ? 0.06 : 0.13);

      // 期号徽章
      const badge = K.sp(svg, "g", {});
      K.sp(badge, "circle", { cx: bxc2, cy: byc2, r: 92,
        fill: LT ? "#FFFFFF" : "#0C1B2E", stroke: GOLD, "stroke-width": 5 });
      K.sp(badge, "circle", { cx: bxc2, cy: byc2, r: 74, fill: "none",
        stroke: GOLD, "stroke-width": 2, opacity: .55 });
      const bt = K.sp(badge, "text", { x: bxc2, y: byc2 + 16, fill: GOLD, "font-size": 38,
        "font-weight": 900, "text-anchor": "middle" });
      bt.textContent = no;

      // 两句胶囊：避开字幕安全区
      const done = chip(box, "装进脑子", GOLD, bxc2, chipY2, 30);
      const brand = chip(box, "关注 脑脑不老佬", GOLD, bxc2, chipY1, 34);

      // ★ 账号符号：脑子。没它就等于没片尾。
      const brain = brainImg(svg, bxc, byc, bwd);

      return { svg, badge, done, brand, brain, bx: bxc2, by: byc2,""",
          "lib: 片尾横屏两栏", idem="const wide = K.VH < 1400;")
    p.sub("      gpop(ctx.badge, K.seg(tl, 0.25, 1.05), 540, 300, 0.4);",
          "      gpop(ctx.badge, K.seg(tl, 0.25, 1.05), ctx.bx || 540, ctx.by || 300, 0.4);",
          "lib: 徽章弹出圆心随布局")
    p.save()


def patch_assets(web):
    p = Patcher(os.path.join(web, "js", "assets.js"))
    p.sub('sp(g, "rect", { x: 0, y: 0, width: 1080, height: 1440, filter: `url(#${uid})` });',
          'sp(g, "rect", { x: 0, y: 0, width: K.VW, height: K.VH, filter: `url(#${uid})` });',
          "assets: 雪/落尘全屏层")
    p.sub('return sp(svg, "rect", { x: 0, y: 0, width: 1080, height: 1440, fill: `url(#${uid})` });',
          'return sp(svg, "rect", { x: 0, y: 0, width: K.VW, height: K.VH, fill: `url(#${uid})` });',
          "assets: vignette")
    p.sub("""    return sp(svg, "rect", { x: 0, y: 0, width: 1080, height: 1440,
      filter: `url(#${uid})`, opacity: opacity == null ? 0.05 : opacity });""",
          """    return sp(svg, "rect", { x: 0, y: 0, width: K.VW, height: K.VH,
      filter: `url(#${uid})`, opacity: opacity == null ? 0.05 : opacity });""",
          "assets: grain")
    p.save()


def patch_engine(web):
    p = Patcher(os.path.join(web, "js", "engine.js"))
    p.sub('  const stage = document.getElementById("stage");',
          """  const stage = document.getElementById("stage");
  // 画布尺寸由 timeline.json 决定（竖屏 1080×1440 / 横屏 1440×1080），CSS 只做兜底
  stage.style.width = K.VW + "px"; stage.style.height = K.VH + "px";
  if (K.VH < 1400) {                    // 横屏 4:3：字幕更宽更矮，字号小一档
    subBox.style.left = "110px"; subBox.style.width = (K.VW - 220) + "px";
    subBox.style.bottom = "84px"; subBox.style.fontSize = "46px";
    subBox.style.lineHeight = "1.45";
  }""", "engine: 舞台与字幕随尺寸", idem="stage.style.width = K.VW")
    p.sub("const s = Math.min(innerWidth / 1080, innerHeight / 1440) * (CAPTURE ? 1 : 0.94);",
          "const s = Math.min(innerWidth / K.VW, innerHeight / K.VH) * (CAPTURE ? 1 : 0.94);",
          "engine: 窗口缩放适配")
    p.sub('"position:absolute;left:-99999px;top:0;width:1080px;height:1440px;overflow:hidden";',
          '"position:absolute;left:-99999px;top:0;width:" + K.VW + "px;height:" + K.VH + "px;overflow:hidden";',
          "engine: 音效预扫描离屏容器")
    p.save()


TL_HEAD = """const __TLJ = JSON.parse(fs.readFileSync(path.join(HERE, "timeline.json"), "utf8"));
const __VW = __TLJ.width || 1080, __VH = __TLJ.height || 1440;
"""


def patch_mjs(web, fn, vp_old, vp_new, anchor):
    p = Patcher(os.path.join(web, fn))
    p.sub(anchor, anchor + "\n" + TL_HEAD, "%s: 读 timeline 尺寸" % fn, idem="const __TLJ")
    p.sub(vp_old, vp_new, "%s: viewport" % fn)
    p.save()


def patch_tools(web):
    patch_mjs(web, "capture.mjs",
              "  await page.setViewport({ width: 1080, height: 1440, deviceScaleFactor: 1 });",
              "  await page.setViewport({ width: __VW, height: __VH, deviceScaleFactor: 1 });",
              'const HERE = path.dirname(fileURLToPath(import.meta.url));')
    patch_mjs(web, "_check.mjs",
              'await page.setViewport({ width: 1080, height: 1440, deviceScaleFactor: 1 });',
              'await page.setViewport({ width: __VW, height: __VH, deviceScaleFactor: 1 });',
              'const HERE = path.dirname(fileURLToPath(import.meta.url));')
    patch_mjs(web, "_overlap.mjs",
              'await page.setViewport({ width: 1080, height: 1440, deviceScaleFactor: 1 });',
              'await page.setViewport({ width: __VW, height: __VH, deviceScaleFactor: 1 });',
              'const HERE = path.dirname(fileURLToPath(import.meta.url));')
    patch_mjs(web, "_gcheck.mjs",
              'await page.setViewport({ width: W, height: H, deviceScaleFactor: 1 });',
              'await page.setViewport({ width: __VW, height: __VH, deviceScaleFactor: 1 });',
              'const HERE = path.dirname(fileURLToPath(import.meta.url));')
    # _gcheck 的 W/H/SAFE_BOT 要跟着变
    p = Patcher(os.path.join(web, "_gcheck.mjs"))
    p.sub("const W = 1080, H = 1440, SAFE_BOT = 1140;",
          'const W = __VW, H = __VH, SAFE_BOT = __VH >= 1400 ? 1140 : 800;',
          "_gcheck: 越界阈值")
    p.save()
    # _overlap 的字幕区上沿
    p = Patcher(os.path.join(web, "_overlap.mjs"))
    p.sub('const SUB_TOP = parseFloat(arg("--sub", "1170"));',
          'const SUB_TOP = parseFloat(arg("--sub", String(__VH >= 1400 ? 1170 : 800)));',
          "_overlap: 字幕区上沿")
    p.save()

    # _check / _gcheck 里还有写死的 1088 / 1448 / 1070 / 1430 / 1020 / 1380（越界判定用），
    # 换成传进来的画布尺寸，否则横屏下每一帧都报假越界。
    p = Patcher(os.path.join(web, "_check.mjs"))
    p.sub("const isFullBleed = !isLeafText && (r2.width >= 1070 || r2.height >= 1430);",
          "const isFullBleed = !isLeafText && (r2.width >= VW - 10 || r2.height >= VH - 10);",
          "_check: 出血豁免阈值", idem="r2.width >= VW - 10")
    p.sub("r2.right > 1088 || r2.bottom > 1448",
          "r2.right > VW + 8 || r2.bottom > VH + 8",
          "_check: 越界阈值", idem="r2.right > VW + 8")
    p.sub("  const r = await page.evaluate((tt) => {",
          "  const r = await page.evaluate((tt, VW, VH) => {",
          "_check: 传入画布尺寸", idem="evaluate((tt, VW, VH)")
    p.sub("  }, t);\n  rows.push(", "  }, t, __VW, __VH);\n  rows.push(",
          "_check: 传参", idem="t, __VW, __VH);\n  rows.push(")
    p.save()

    p = Patcher(os.path.join(web, "_gcheck.mjs"))
    p.sub("    const r = await page.evaluate((tt, SAFE_BOT) => {",
          "    const r = await page.evaluate((tt, SAFE_BOT, VW, VH) => {",
          "_gcheck: 传入画布尺寸", idem="evaluate((tt, SAFE_BOT, VW, VH)")
    p.sub("if (b.width >= 1020 || b.height >= 1380) continue;",
          "if (b.width >= VW * 0.94 || b.height >= VH * 0.94) continue;",
          "_gcheck: 出血豁免阈值", idem="b.width >= VW * 0.94")
    p.sub("b.x + b.width + sw > 1082 || b.y + b.height + sw > 1442;",
          "b.x + b.width + sw > VW + 2 || b.y + b.height + sw > VH + 2;",
          "_gcheck: 越界阈值", idem="b.x + b.width + sw > VW + 2")
    p.sub("    }, t, SAFE_BOT);", "    }, t, SAFE_BOT, W, H);",
          "_gcheck: 传参", idem="t, SAFE_BOT, W, H);")
    p.save()
    # _shot 的 W/H
    p = Patcher(os.path.join(web, "_shot.mjs"))
    if "__TLJ" not in p.text:
        p.sub('const HERE = path.dirname(fileURLToPath(import.meta.url));',
              'const HERE = path.dirname(fileURLToPath(import.meta.url));\n' + TL_HEAD,
              "_shot: 读 timeline 尺寸")
    p.sub("const W = 1080, H = 1440;", "const W = __VW, H = __VH;", "_shot: 画布尺寸")
    p.save()


def patch_gen_timeline(web):
    p = Patcher(os.path.join(web, "gen_timeline.py"))
    if "size.json" not in p.text:
        p.sub('    out = {"fps": 30, "width": 1080, "height": 1440, "duration": duration,',
              '    out = {"fps": 30, "width": WIDTH, "height": HEIGHT, "duration": duration,',
              "gen_timeline: 尺寸走配置")
        # 在 module 顶部注入 WIDTH/HEIGHT
        txt = p.text
        m = re.search(r"^HERE *= *.*$", txt, re.M)
        if not m:
            raise SystemExit("✗ gen_timeline.py 找不到 HERE 定义")
        ins = (m.group(0) + "\n\n"
               "# 画布尺寸：默认竖屏 3:4，同目录 size.json 可覆盖（横屏 4:3 = 1440×1080）\n"
               "WIDTH, HEIGHT = 1080, 1440\n"
               "try:\n"
               "    _sz = json.load(open(os.path.join(HERE, \"size.json\"), encoding=\"utf-8\"))\n"
               "    WIDTH, HEIGHT = int(_sz[\"width\"]), int(_sz[\"height\"])\n"
               "except Exception:\n"
               "    pass\n")
        p.text = txt.replace(m.group(0), ins, 1)
        p.log.append("  ✓ gen_timeline: 注入 WIDTH/HEIGHT")
    p.save()


def patch_timeline_json(web, w, h):
    jp = os.path.join(web, "timeline.json")
    j = json.load(open(jp, encoding="utf-8"))
    j["width"], j["height"] = w, h
    json.dump(j, open(jp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    js = "window.TIMELINE=" + json.dumps(j, ensure_ascii=False) + ";"
    open(os.path.join(web, "timeline.js"), "w", encoding="utf-8").write(js)
    print("  ✓ timeline.json/js 尺寸 -> %d×%d" % (w, h))


def convert(ep, w, h):
    web = os.path.join(PROD, ep, "web")
    if not os.path.isdir(web):
        print("✗ 没有 %s" % web); return
    print("== %s -> %d×%d" % (ep, w, h))
    json.dump({"width": w, "height": h},
              open(os.path.join(web, "size.json"), "w", encoding="utf-8"))
    patch_kit(web); patch_lib(web); patch_assets(web); patch_engine(web)
    patch_tools(web); patch_gen_timeline(web)
    patch_timeline_json(web, w, h)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:]]
    w = int(args[args.index("--w") + 1]) if "--w" in args else 1440
    h = int(args[args.index("--h") + 1]) if "--h" in args else 1080
    tgt = EPS if "--all" in args else [a for a in args if a.startswith("NO.")]
    if not tgt:
        print(__doc__); sys.exit(1)
    for ep in tgt:
        if ep == "NO.23":
            convert("NO.23_蒙眼分硬币", w, h)
        else:
            hit = [e for e in EPS if e.startswith(ep)]
            convert(hit[0] if hit else ep, w, h)
