"""_wcheck.py — 校验 scenes.js 里的时间锚点 W(shot, 行号, "关键词") 是否对得上台词。

为什么需要它（2026-10-21 NO.11 的病根，2026-10-24 重写文案时又踩了一次）：
    W(shot, i, "kw") 的语义是「第 i 行台词念到 kw 这个词的时刻」。
    一旦改了台词，kw 匹配不到，W() 就返回 undefined，
    跟着 K.seg(tl, undefined, ...) 得到 NaN → 那个元素**永远不显示**。
    整段画面变成空白/静止，但渲染不报错、截图也照常生成。
    肉眼只能看出「这镜头好像没动」，机器不看就发现不了。

用法：python _wcheck.py v11_rosenhan
退出码 0 = 全部锚点都能匹配上。
"""
import importlib.util, os, re, sys

from _paths import proj_dir   # 期工程目录（新旧兼容）


def load_shots(proj):
    f = os.path.join(proj_dir(proj), "script.py")
    spec = importlib.util.spec_from_file_location("s", f)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    # 场景名怎么取？
    #   ★ 2026-10-26 修正：引擎（engine.js）用的是 `Scenes[shot.scene]`，
    #   而 timeline 里的 scene 是 "YouScene" -> "you"。所以**权威来源是 scene 字段**。
    #   原来这里只按 id 后缀取（02_hear -> hear），撞上「换了镜头顺序、id 跟着改」
    #   就会整镜报「scenes.js 里的场景名在 script.py 里找不到对应镜头」——
    #   那其实是假报，动画是好的，工具自己把真问题淹了。
    #   现在：scene 字段优先，取不到再退回 id 后缀（老期不受影响）。
    out = {}
    for sh in m.SHOTS:
        key = None
        sc = sh.get("scene")
        if sc:
            key = re.sub(r"Scene$", "", sc).lower()
        if key not in out:
            alt = sh["id"].split("_", 1)[1]
            if key is None:
                key = alt
            elif alt not in out:
                out.setdefault(alt, sh["lines"])
        out[key] = sh["lines"]
    return out


def main():
    proj = sys.argv[1] if len(sys.argv) > 1 else "v11_rosenhan"
    shots = load_shots(proj)
    js_path = os.path.join(proj_dir(proj), "web", "js", "scenes.js")
    js = open(js_path, encoding="utf-8").read()

    # 按 define("name" 切段，判定每个 W() 属于哪个场景
    marks = [(m.start(), m.group(1)) for m in re.finditer(r'define\("([a-z0-9_]+)"', js)]
    marks.append((len(js), None))
    bad = []
    total = 0
    for i in range(len(marks) - 1):
        st, name = marks[i]
        seg = js[st:marks[i + 1][0]]
        if name not in shots:
            bad.append((name, "-", "scenes.js 里的场景名在 script.py 里找不到对应镜头"))
            continue
        lines = shots[name]
        # 两种写法都要认：W(shot, ...) 和 W(sh, ...)（NO.17 里用 sh 做局部别名）。
        # 2026-10-24 发现：只认 shot 会漏掉整期 0 个锚点还报 OK，等于白查。
        for m in re.finditer(r'W\(\s*(?:shot|sh)\s*,\s*([^,]+?),\s*"([^"]*)"\)', seg):
            total += 1
            arg, kw = m.group(1).strip(), m.group(2)
            if arg.isdigit():
                idx = int(arg)
                if idx >= len(lines):
                    bad.append((name, idx, '越界：这镜只有 %d 行台词' % len(lines)))
                elif kw not in lines[idx]:
                    # 允许去掉空格后再比（台词里常写「12 家医院」，关键词写「12家」）
                    if kw.replace(" ", "") not in lines[idx].replace(" ", ""):
                        bad.append((name, idx, '「%s」不在这行：%s' % (kw, lines[idx][:34])))
            else:
                # shot.lines.length - 1 这类动态索引，只检查关键词是否出现在最后一行的语义
                last = lines[-1]
                if kw.replace(" ", "") not in last.replace(" ", ""):
                    bad.append((name, arg, '「%s」不在末行：%s' % (kw, last[:34])))

    print("%s：检查 %d 个时间锚点" % (proj, total))
    if bad:
        print("\n[FAIL] %d 处对不上（这些动画会静默失效）：" % len(bad))
        for name, idx, why in bad:
            print("  · %-10s 第 %-4s 行  %s" % (name, idx, why))
        return 1
    print("[OK] 所有锚点都能匹配到台词")
    return 0


if __name__ == "__main__":
    sys.exit(main())
