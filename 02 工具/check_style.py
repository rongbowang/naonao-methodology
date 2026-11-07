# -*- coding: utf-8 -*-
"""文案风格自检 —— 对应《文案创作法 v1》第二、三章
用法:
    python check_style.py script.py

检查项:
  1. 钩子：前 12 字是否有具体人名/数字/反常识；是否出现自我介绍式开场
  2. 句长：是否连续 4 句都落在 12~20 字（AI 味的头号特征）
  3. 是否至少有 1 句 <=6 字的短句
  4. 禁词命中（书面连接词 / 空转形容词 / 序数词）
  5. 人称：'你' 次数、'我/我们' 次数
  6. 人名数量估计（>3 提示）
退出码: 0 = 无硬性违规（禁词与人名需人工判断时会给出 WARN）；1 = 有硬性违规
"""
import re
import sys

# ---------------- 规则表 ----------------
BAN_CONNECT = ["因此", "然而", "正是", "综上", "与此同时", "不难发现", "由此",
               "可见", "从而", "众所周知", "值得一提的是", "基于此", "换言之"]
BAN_ADJ = ["优美", "精妙", "神奇", "震撼", "令人惊叹", "不可思议", "叹为观止",
           "淋漓尽致", "美轮美奂", "叹为观止的"]
BAN_ORDINAL = ["首先", "其次", "最后", "第一，", "第二，", "第三，"]

# ===== AI 八股硬检查（2026-10-23，参照 op7418/Humanizer-zh 31 条 + ren644 黑名单）=====
# 为什么加：用户反馈「文案写得不是特别好」，扫下来最刺眼的是两样 ——
#   ① 「你敢信吗 / 你敢相信吗」在 6 期里用了 6 次，本身就是模板化
#   ② 「不是X，是Y」踩 Humanizer 的第一条禁令（假装对比抬高语气）
# 表里的规则都是可直接判定的，判不了的不放（宁可少抓，不要误报）。

# ① 引导语式钩子：先招呼再说话，等于把「炸的那一帧」让给了一句废话
LEAD_HOOK = ["你敢信吗", "你敢相信吗", "你可能不信", "你肯定不信", "你大概不信",
             "你知道吗", "你不知道的是", "你敢想象", "说出来你可能不信"]

# ② 假对比：「不是A，是B」——两句说的其实是同一件事，否定那半只用来抬高语气
NOT_X_BUT_Y = [
    r"不是[^，。！？]{1,14}，?而是", r"不是[^，。！？]{1,14}，是",
    r"不仅[^，。]{1,12}更是", r"与其说[^，。]{1,12}不如说",
]

# ③ 意义拔高：把一件具体的事说到「时代 / 意义 / 里程碑」上去
ALTITUDE = ["标志着", "彰显", "见证了", "时代的", "新纪元", "划时代", "里程碑",
            "开创了", "树立了", "奠定了基础", "意义深远", "影响深远"]

# ④ 起跑式铺垫：预告接下来要讲什么，本身就是空转
RUNUP = ["接下来", "下面我们", "下面来看", "让我们", "我们来看看", "我们来说说",
         "说到这儿", "话不多说", "不妨", "且看"]

# ④-b 编排话 / 元叙述（2026-11-03 用户第 N 次发火后加，硬 FAIL）
#    「先把规矩说死」「下面我们分成三步」这类句子，说的是"我要讲什么"，
#    不是内容本身。观众点进来不是听你排版的。
#    判据：句子里出现「先说 + 规矩/规则/结论/条件」或下面这些现成套话，一律不许。
METATALK = ["先把规矩", "把规矩说死", "规矩先说", "先说规矩", "先讲规矩",
            "先把规则", "先立规矩", "定个规矩", "先说结论", "先把话说死",
            "下面进入", "接下来我们", "我们分成", "分三步", "先看第一条",
            "第一步，", "第二步，", "第三步，", "先说三条", "规矩就一条",
            # 2026-11-03 用户第二轮回炉补的四类（他自己总结的判定标准：
            # 「只要句子在说'我要开始讲了'，不在讲这件事本身，就删」）
            "关键在这儿", "关键在于", "还有一层", "再进一层", "举个例子", "比如说吧",
            "先说清楚", "换一套走法", "换个走法", "换个问法", "换个方向", "换种说法",
            "重点是", "核心是", "说白了", "简单说", "注意这里", "这里要注意",
            "有意思的是", "值得注意的是"]
METATALK_RE = re.compile(r"先(把|说|讲|立)(一下)?(规矩|规则|条件|结论|前提)")

# ⑤ 套话收尾
WRAPUP = ["总之", "总的来说", "归根结底", "拭目以待", "由此可见",
          "这就是.{0,8}的本质", "这才是.{0,8}的真相"]

# ⑥ AI 高频空词（只在单独成句/作修饰时才算，术语里出现不管）
AI_WORD = ["深入", "无缝", "闭环", "赋能", "底层逻辑", "范式", "生态位",
           "链路", "抓手", "护城河", "降维打击", "弯道超车", "认知升级"]
SELF_INTRO = ["今天我们来", "大家好", "欢迎来到", "我是", "这期我们", "本期我们",
              "今天我们聊", "话不多说", "开始之前"]

# ===== 第一人称"个人感受 / 个人反应"黑名单（用户 2026-10-19 硬要求）=====
# 为什么要禁：把"数据有多震撼"外包给作者的身体反应（愣住 / 后背发凉 / 盯着看了半天），
# 观众并不会跟着震撼，只会觉得"那是你的事"；而且它把科普口播降级成个人体验分享，
# 专业度直接掉一档。数据冲击力必须由数据本身 + 画面 + 对撞句承担。
# 三层判据：
#   A 身体/情绪反应词：愣、怔、后背发凉、起鸡皮、看呆、打死不信 …
#   B 个人认知自述：我以前（以为/觉得）、我一开始、我当时、我个人 …
#   C 个人阅读/观看动作：我第一次看到、我看完、我读完、我查完 …
FP_FEEL = ["愣", "怔", "懵", "后背", "头皮", "发凉", "鸡皮", "心里一", "说实话",
           "目瞪口呆", "看呆", "吓一跳", "看了半天", "盯了半天", "读了好几遍",
           "反复看", "失眠", "睡不着", "怀疑人生", "打死不信", "不敢信", "坐不住",
           "揪心", "堵得慌", "不寒而栗", "服了", "傻了"]
FP_ME = ["我以前", "我一开始", "我当年", "我当时", "我个人", "我第一",
         "我看完", "我读完", "我查完", "我原来以为", "我原以为"]
FP_ME2 = ["我", "咱"]

# 合法的"我/我们"：只剩「泛指共识立靶」和「论文转述」两种
# （"实验背书"已从白名单移除，见下面的 FP_CLAIM）
FP_OK = ["我们一直", "我们总", "我们都", "我们习惯", "我们以为", "我们默认",
         "我们后来", "我们分不清", "我们没法", "我们可能", "换成我们",
         "陪了我们", "离我们", "在我们", "告诉我们", "我们太", "我们从小",
         "我们身边", "我们眼前"]

# ===== 第一人称"实验 / 考察背书"黑名单（用户 2026-10-19 追加要求）=====
# 用户原话：不要再说「我们真把它跑了一遍」这种话，
# 改成「计算机结果验证了我们的说法」——**让结果当主语，别让"我们"当主语**。
# 道理：观众不关心谁动的手，只关心结论靠不靠得住；把"我做了"当可信度，
# 既自夸又没信息量。而且一旦夸口"我们真搭了/真跑了"，而实际没做，就是虚假背书。
FP_CLAIM = ["我们真", "真把它跑", "我们跑了", "我们跑了一遍", "我们把它跑",
            "我们做了", "我们搭了", "我们实测", "我们亲手", "我们查了",
            "我们试了", "我们算了", "我们算过", "我们数过", "我们看过原片"]


# 结尾钩子禁用（用户 2026-10-17 硬要求，见《文案创作法》4.1 / 4.7）：
#   一组 = 铺垫话术；一组 = 直给答案的连接；一组 = 抽象虚词（画不成画面，钩子会变软）
TEASER_BAN = ["今天我们", "今天我们来", "接下来", "下面我们",
              "本期我们", "让我们来看看", "先来说说",
              "代价是", "结果是", "原因是", "正是因为", "也就是说", "换句话说",
              "难言之隐", "这笔账", "无法想象", "不禁", "莫名", "一种说不出的",
              "无法用语言", "说不清道不明"]

NAMES = ["牛顿", "伽利略", "爱因斯坦", "伯努利", "莱布尼茨", "洛必达", "惠更斯",
         "欧拉", "拉格朗日", "开尔文", "达尔文", "鲍林", "霍伊尔", "伽伐尼",
         "沃尔塔", "罗森汉", "米尔格拉姆", "津巴多", "福勒", "姆潘巴", "奥斯本",
         "卡茨", "萨根", "哈勃", "弗里德曼", "勒迈特", "亚里士多德", "孟德尔",
         "爱因斯坦", "图灵", "冯诺依曼", "香农", "纳什", "西蒙", "卡尼曼"]

PUNCT = "，。！？；：、…—·「」『』《》（）()\"'.,!?;: \u3000"
LONG_MIN = 12             # 长句阈值（≥12 字算"一口气长句"）
LONG_PEAK = 14            # 全片至少要出现一次这么长的句子（2026-11-01：18->14，18 字与 12 字呼吸线冲突）
LONG_RATIO = 0.15         # 长句占比下限
CHOP_LO, CHOP_HI = 5, 10  # 最容易变成"AI 匀速感"的区间
CHOP_RUN = 8              # 连续这么多句都落在均匀区间 -> 提示（2026-11-01：6->8，与 12 字呼吸线相容）
SHORT_MAX = 6             # 短句（口语碎片）阈值
SHORT_RATIO = 0.12        # 短句占比下限


def load_shots(path):
    ns = {}
    exec(compile(open(path, encoding="utf-8").read(), path, "exec"), ns)
    return ns["SHOTS"], ns.get("OUTRO_HOOK", None), ns


def clean(t):
    return re.sub("[" + PUNCT + "]", "", t)


def split_units(text):
    return [u for u in re.split("[" + PUNCT + "]+", text) if clean(u)]


def split_sents(text):
    return [u for u in re.split("[。！？]+", text) if clean(u)]


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "script.py"
    shots, outro_hook, ns = load_shots(path)
    lines = []
    for s in shots:
        lines.extend(s["lines"])
    # 片尾预告的钩子句（outro 镜的倒数第 2 句）自 2026-10-20 起由用户亲自撰写，
    # 机器不改也不判它 —— 从正文检查里剔除，否则「你敢信吗」这类引导语会把整篇判 FAIL。
    outro_hook_line = ""
    for s in shots:
        if "outro" in s["id"] and len(s["lines"]) >= 2:
            outro_hook_line = s["lines"][-2]
    full = "".join(ln for ln in lines if ln != outro_hook_line)
    units = []
    for ln in lines:
        if ln == outro_hook_line:
            continue
        units.extend(split_units(ln))
    sents = []
    for ln in lines:
        if ln == outro_hook_line:
            continue
        sents.extend(split_sents(ln))

    fails, warns, style = [], [], []   # style = 风格参考分，不进入返工流程（2026-11-01）

    # 0) 爆点声明 —— 按《文案创作法》3.0：动笔写钩子之前，先找出这个题材的爆点
    #    （三问：① 会不会「啊？」② 会不会「不可能吧」③ 能不能一眼画成画面）
    bd = str(ns.get("BAODIAN", "")).strip()
    bdt = str(ns.get("BAODIAN_TYPE", "")).strip()
    print("爆点: %s  [%s]" % (bd or "（未声明）", bdt or "?"))
    if not bd:
        fails.append("script.py 顶部没有声明 BAODIAN -> 按 3.0 先找爆点；"
                     "找不出爆点说明这个题材不该做（换题）")
    else:
        n_bd = len(clean(bd))
        if n_bd > 40:
            warns.append("爆点 %d 字（>40）-> 爆点要一句话 / 一幅画，越短越狠（3.0）" % n_bd)
        # 爆点的"裸度"：不许带解释尾巴（机制 / 换算 / 后文结论）——那等于把答案说了
        TAIL = ["因为", "所以", "等于", "也就是说", "原因是", "这是", "那是",
                "其实", "原来", "是为了", "正是"]
        hit = [w for w in TAIL if w in bd]
        if hit:
            fails.append("爆点带了『解释尾巴』（%s）-> 按 3.0「爆点的裸度」砍掉尾巴，"
                         "只留最生猛的那一帧画面" % "、".join(hit))
        # 测量值：报精确参数 = 在念实验记录，不是在制造损失（3.0 改写手术①）
        m = re.search(r"\d+(?:\.\d+)?\s*(厘米|毫米|公里|千克|公斤|吨|千克|米)", bd)
        if m:
            warns.append("爆点里有测量值「%s」-> 八成是在报参数；换成「损失 / 一幅画」"
                         "（3.0 改写手术①：地球正在失去月亮 ＞ 一年 3.8 厘米）" % m.group(0))
        if bdt not in ("P1", "P2", "P3", "P4", "P5", "P6"):
            fails.append("BAODIAN_TYPE 不是 P1~P6（3.0 六型：荒谬事实/权威翻车/常识背叛/"
                         "数字离谱/小人物逆袭/身份错位）")
        # 弱关联：钩子必须"对准"爆点 —— 两者至少共用一个 >=2 字的词
        seg_hook = set(re.findall(r"[\u4e00-\u9fff]{2,}", clean(lines[0])))
        seg_bd = set(re.findall(r"[\u4e00-\u9fff]{2,}", clean(bd)))
        share = set()
        for x in seg_hook:
            for y in seg_bd:
                for k in range(len(x) - 1):
                    if x[k:k + 2] in y:
                        share.add(x[k:k + 2])
                        break
        if not share:
            warns.append("开头钩子和爆点没有任何共同词 -> 确认钩子是不是对准了爆点（3.0）")

    # 0) 编排话 / 元叙述（硬 FAIL）—— 说的是"我要讲什么"而不是内容
    for ln in lines:
        c = clean(ln)
        hit = [w for w in METATALK if w in c]
        m2 = METATALK_RE.search(c)
        if hit or m2:
            fails.append("出现编排话「%s」-> 台词里不许说『我要讲什么』，"
                         "直接给内容（2026-11-03 用户明令）" % (hit[0] if hit else m2.group(0)))

    # 1) 钩子 —— 按《文案创作法》3.1「第一句即第三秒」铁律：
    #    不再要求前 12 字有人名/数字（数字平铺本身已是禁令），改为直接查三条禁令
    hook = lines[0]
    head12 = clean(hook)[:12]
    print("钩子首句: %s" % hook)
    print("  前 12 字: %s" % head12)
    BAN_FRAME = ["教科书", "论文", "研究表明", "据统计", "你肯定听过",
                 "众所周知", "有句话说", "书上说"]
    for w in BAN_FRAME:
        if w in hook:
            fails.append("钩子出现『%s』式铺垫/引用（3.1 禁令②）" % w)
    m_year = re.search(r"(1[5-9]\d\d|20\d\d)\s*年", hook)
    if m_year:
        # 2026-10-21：钩子改由用户定稿，人物型钩子（"1799年，华盛顿…"）允许带年份，只提示
        warns.append("钩子里出现年份「%s」-> 若无必要可删，人物型钩子可保留（3.1 禁令①，WARN）" % m_year.group(0))
    if len(clean(hook)) > 30:
        warns.append("钩子首句 %d 字（>30）-> 3.0「能少给就少给」：信息给多了，" 
                     "能砍成半句就砍（目标 15~25 字）" % len(clean(hook)))
    # 钩子不许"给答案"（3.0 爆点≠钩子）：出现因果连接，多半把"为什么"也说出来了
    CAUSAL = ["因为", "所以", "导致", "于是", "之所以", "从而", "结果是", "原因是"]
    hit_c = [w for w in CAUSAL if w in hook]
    if hit_c:
        warns.append("开头钩子里有因果连接（%s）-> 检查是不是把『为什么』也说了；"
                     "钩子只该留一半（3.0 爆点≠钩子）" % "、".join(hit_c))
    if bd and clean(hook) == clean(bd):
        fails.append("开头钩子 = 爆点原文 -> 等于把答案整个说了（3.0 爆点≠钩子，要切掉一块）")
    for s in SELF_INTRO:
        if s in hook:
            fails.append("钩子出现自我介绍式开场「%s」" % s)

    # 1c) 钩子必须是"结论句"而不是"前提句"（2026-10-20 视频分析反馈，见《文案创作法》3.12）
    #     判据：句子里至少有「转折 / 极值 / 否定 / 对撞」之一，才算自带结论。
    #     只有条件、只有场景、只有名词陈列 —— 那是前提句，观众要等几秒才 get 到矛盾。
    HOOK_MARK = ["却", "反而", "竟然", "居然", "反倒", "倒着", "逆着", "反过来",
                 "最", "全", "都", "没", "无", "只", "唯一", "从不", "再也",
                 "根本", "完全", "整个", "任何", "一点不", "一个不",
                 "还", "比", "不如", "多过", "超过"]
    if not any(w in hook for w in HOOK_MARK):
        warns.append("钩子首句没有任何「转折 / 极值 / 否定」标记 -> 很可能只是前提句，"
                     "不是结论句。改成一句自带对撞的结论（3.12-A）："
                     "✗『两台老虎机，单玩都输』 ✓『一台单玩必输的机器，换着玩反而赢』")

    # 1a) 片尾「恭喜」句必须说清「第 N 个什么」（用户 2026-10-20 点名：缺宾语）
    CONGRA_OBJ = ["知识", "冷知识", "思维模型", "道理", "结论", "概念"]
    for t in shots[-1]["lines"]:
        if "恭喜" in t and "装进脑子" in t and not any(o in t for o in CONGRA_OBJ):
            fails.append("片尾「%s」缺宾语 -> 说清是「第 N 个什么」装进脑子了（2026-10-20）" % t)

    # 1b) 结尾钩子（第四·0 / 4.1 节）：不许铺垫、不许放答案、18~30 字、≤6 秒
    tail = [t for t in shots[-1]["lines"] if "关注" not in t]
    idx = next((i for i, t in enumerate(tail)
                if any(k in t for k in ("下一期", "明天", "下期"))), len(tail) - 1)
    teaser = tail[idx:] if tail else []
    # 2026-10-21：用户要求「抛下期钩子之前，先报一句过渡」，否则钩子突兀。
    # 这句只是转折信号，不是钩子本身 —— 整句剔掉，不占 18~30 字 / 6 秒预算。
    TRANS = re.compile(r"^(下一期|下期|明天)[，,:：]?(我们|咱们|咱|我)?(来|接着|再|说)?"
                       r"(看|讲|聊)[^。！？]{0,6}[。！？]?$")
    teaser = [t for t in teaser if not TRANS.match(t.strip())] or teaser
    joined = "".join(teaser)
    print("结尾预告: %s" % " / ".join(teaser))
    # 期号不算"数字钩子"：先剔掉 "第 N 个" / "NO.0N" / 开头的"下一期："
    probe = re.sub(r"第\s*\d+\s*个?", "", joined)
    probe = re.sub(r"NO\.?\s*\d+", "", probe)
    # 2026-10-26：片尾改成三句版，「过渡句」和钩子合并成
    # 「下一期我们来看：<问句>」，所以「我们来看」这几个字也要剔掉，不算进字数预算
    probe = re.sub(r"^\s*(下一期|明天|下期)\s*(我们|咱们|咱|我)?\s*"
                   r"(来|接着|再|说)?\s*(看|讲|聊)?\s*[：:，,]?", "", probe.strip())
    n_teaser = len(clean(probe))
    est = n_teaser / 4.2
    print("  正文 %d 字  预估 %.1f 秒（按 4.2 字/秒）" % (n_teaser, est))
    for w in TEASER_BAN:
        if w in joined:
            fails.append("结尾钩子出现铺垫 / 直给答案的「%s」-> 重写（第四·1 节第 1、5 条）" % w)
    if n_teaser > 30:
        fails.append("结尾钩子 %d 字（>30）-> 压到 18~30 字（第四·1 节第 4 条）" % n_teaser)
    elif n_teaser < 12:
        warns.append("结尾钩子只有 %d 字 -> 建议 18~30 字（第四·1 节第 4 条）" % n_teaser)
    # 2026-10-20：疑问引子型钩子（"你敢信吗？…"）天然多占 1 秒，上限放到 6 秒
    if est > 6.0:
        fails.append("结尾钩子估时 %.1f 秒（>6 秒）-> 压到 6 秒内（第四·1 节第 4 条）" % est)
    # 第四·1 节第 2 条：预告必须含「人 / 数 / 反差」三要素之一
    CONTRAST = ["代价", "却", "反而", "竟然", "居然", "再也", "全被", "全没",
                "一个都没", "根本", "活活", "错", "假", "谁也没", "没有一个人",
                "最后", "然后", "只剩下"]
    t_ok = (bool(re.search(r"\d", probe)) or any(n in probe for n in NAMES)
            or any(k in probe for k in CONTRAST))
    if not t_ok:
        # 2026-10-21：钩子改由用户亲自撰写，口语反问/劝告型（"为什么…""别再…"）同样成立，
        # 这条自动判据只作提示，不再阻断。
        warns.append("结尾预告里没有『人名 / 数字 / 反差』-> 机器判不了它勾不勾人，请人工确认（第四·1 节）")

    # 2) 节奏：均匀 = AI 味
    lens = [len(u) for u in units]
    chop = longest_chop = 0
    for L in lens:
        chop = chop + 1 if CHOP_LO <= L <= CHOP_HI else 0
        longest_chop = max(longest_chop, chop)
    if longest_chop >= CHOP_RUN:
        style.append("连续 %d 句句长都落在 %d~%d 字（节奏偏匀速）-> 参考分，不阻断"
                     % (longest_chop, CHOP_LO, CHOP_HI))
    n_tot = max(len(lens), 1)
    n_long = sum(1 for L in lens if L >= LONG_MIN)
    n_short = sum(1 for L in lens if L <= SHORT_MAX)
    if n_long / n_tot < LONG_RATIO:
        # 2026-10-23：这条阈值没有硬依据（中文口播的小句天然短，「一口气长句」在
        # 逗号即断句的中文里本来就少），降级为提示，不再阻断。防「匀速」的主力是
        # 上面的 CHOP_RUN 和下的 SHORT_RATIO。
        warns.append("长句（>=%d 字）只占 %.0f%%（参考值 %.0f%%）-> 全篇偏碎，"
                     "看看能不能合并一两处小句" % (LONG_MIN, 100.0 * n_long / n_tot, 100.0 * LONG_RATIO))
    if n_short / n_tot < SHORT_RATIO:
        style.append("短句（<=%d 字）只占 %.0f%%（下限 %.0f%%）-> 参考分"
                     % (SHORT_MAX, 100.0 * n_short / n_tot, 100.0 * SHORT_RATIO))
    if lens and max(lens) < LONG_PEAK:
        warns.append("最长句只有 %d 字（建议至少出现 1 句 >=%d 字，但不得超过 _pause.py 的 16 字硬线）" % (max(lens), LONG_PEAK))

    # 3) 禁词
    for w in BAN_CONNECT:
        if w in full:
            fails.append("书面连接词「%s」（第 3 条）" % w)
    for w in BAN_ADJ:
        if w in full:
            fails.append("空转形容词「%s」（第 9 条）" % w)
    for w in BAN_ORDINAL:
        if w in full:
            warns.append("疑似序数词「%s」（第 5 条），确认是否可改成因果推进" % w)

    # 4) 人称
    #    2026-10-19 调整：原来要求「我/我们 ≥3 次」，等于逼着写稿在结尾段加"我看完…"来凑数，
    #    这正是个人感受句泛滥的机制性诱因。现在把配额转给「你」（观众卷入），
    #    「我」只保留 1 次的余量给"泛指共识 / 实验背书 / 论文转述"。
    n_you = full.count("你")
    n_me = full.count("我")
    if n_you < 5:
        fails.append("「你」只出现 %d 次 -> 至少要 5 处直接对观众说话（第 7 条）" % n_you)
    if n_me < 1:
        fails.append("「我/我们」一次都没有 -> 至少要 1 处泛指共识或论文转述（第 6 条）" % ())

    # 4b) 第一人称"个人感受 / 个人反应"—— 硬禁
    fp_hits = []
    for ln in lines:
        if not any(m in ln for m in FP_ME2):
            continue
        if any(k in ln for k in FP_OK):
            continue
        hit = [w for w in FP_FEEL if w in ln] + [w for w in FP_ME if w in ln]
        if hit:
            fp_hits.append((ln, sorted(set(hit))))
    if fp_hits:
        fails.append("出现 %d 处「第一人称个人感受/反应」—— 不许用『我愣住了 / 我看完后背发凉 / "
                     "我以前一直以为』来烘托数据冲击力；改成数据对撞、画面或直接把判断给观众"
                     "（2026-10-19 整改原则）" % len(fp_hits))
        for ln, hit in fp_hits:
            print("     [个人感受] %s   ← 命中 %s" % (ln, "、".join(hit)))

    # 4c) 第一人称"实验 / 考察背书"—— 硬禁（2026-10-19 用户追加要求）
    claim_hits = []
    for ln in lines:
        hit = [w for w in FP_CLAIM if w in ln]
        if hit:
            claim_hits.append((ln, sorted(set(hit))))
    if claim_hits:
        fails.append("出现 %d 处「第一人称实验背书」—— 不要说『我们真把它跑了一遍 / "
                     "我们真搭了两条轨道 / 我们查了一下』；让结果当主语："
                     "『计算机结果验证了我们的说法』『模拟跑出来的曲线是……』"
                     "（2026-10-19 用户要求）" % len(claim_hits))
        for ln, hit in claim_hits:
            print("     [实验背书] %s   ← 命中 %s" % (ln, "、".join(hit)))

    # 4.5) AI 八股（2026-10-23 新增，参照 Humanizer-zh 31 条）
    lead_hits = [(i, s) for i, s in enumerate(sents) if any(k in s for k in LEAD_HOOK)]
    if lead_hits:
        fails.append("出现 %d 处引导语式钩子（你敢信吗 / 你可能不信 …）—— "
                     "第一句必须是能炸的那一帧本身，不是一声招呼。换掉引导语，"
                     "把后面那半句直接提到第一句" % len(lead_hits))
        for i, s in lead_hits:
            print("     [引导语] 第%d句：%s" % (i + 1, s))

    nx_hits = [(i, s) for i, s in enumerate(sents)
               if any(re.search(r, s) for r in NOT_X_BUT_Y)]
    if nx_hits:
        # Humanizer 原文：「两部分都提供信息，或否定部分纠正真实误解时保留」。
        # 机器分不清「抬语气的假对比」和「真在纠正观众误解」，所以只提示，不阻断。
        warns.append("出现 %d 处「不是X，是Y」—— 逐条确认否定那半是不是在纠正观众"
                     "真实的误解（是就留）；如果只是抬语气，直接说 Y" % len(nx_hits))
        for i, s in nx_hits:
            print("     [假对比] 第%d句：%s" % (i + 1, s))

    alt_hits = [(i, s) for i, s in enumerate(sents) if any(k in s for k in ALTITUDE)]
    if alt_hits:
        fails.append("出现 %d 处意义拔高（标志/彰显/见证/时代…）" % len(alt_hits))
        for i, s in alt_hits:
            print("     [拔高] 第%d句：%s" % (i + 1, s))

    run_hits = [(i, s) for i, s in enumerate(sents) if any(k in s for k in RUNUP)]
    if run_hits:
        fails.append("出现 %d 处起跑式铺垫（接下来 / 让我们 / 下面我们…）" % len(run_hits))
        for i, s in run_hits:
            print("     [起跑式] 第%d句：%s" % (i + 1, s))

    wrap_hits = [(i, s) for i, s in enumerate(sents)
                 if any(re.search(k, s) for k in WRAPUP)]
    if wrap_hits:
        fails.append("出现 %d 处套话收尾（总之 / 归根结底 / 拭目以待…）" % len(wrap_hits))
        for i, s in wrap_hits:
            print("     [套话收尾] 第%d句：%s" % (i + 1, s))

    ai_hits = [(i, s) for i, s in enumerate(sents) if any(k in s for k in AI_WORD)]
    if ai_hits:
        warns.append("出现 %d 处 AI 高频空词（深入/无缝/闭环/赋能/底层逻辑…），"
                     "确认不是行业术语后换掉" % len(ai_hits))
        for i, s in ai_hits:
            print("     [AI词] 第%d句：%s" % (i + 1, s))

    # 4.6) 句长均匀度：全部挤在同一个窄区间，念出来就是「匀速朗读」，AI 味的头号体征
    if len(lens) >= 8:
        import statistics
        sd = statistics.pstdev(lens)
        # 2026-11-01：3.0 -> 2.6，长句参照 18 -> 14。理由：sd>=3.0 靠的是 18 字长句，
        # 与口播「一口气 <=12 字」互斥（历史工程债）。节奏检查保留，但降为参考分。
        if sd < 2.6:
            style.append("句长标准差只有 %.1f（<2.6）—— 节奏偏平，参考分。"
                         "想拉起伏，用「<=8 字短句紧跟 10~14 字中长句」，不要造 18 字长句" % sd)
        elif sd < 3.4:
            warns.append("句长标准差 %.1f，偏均匀，可以再拉开一点" % sd)

    # 4.7) 视频结构约束（2026-10-23）
    # 参照 banger-script-longform / youtube-script-writer / claude-youtube / explainer-videos，
    # 详见 工程文件/视频文案结构约束.md。这几条只提示不阻断 —— 结构判断机器容易误判。
    # S2 承诺句：钩子之后必须有一句回答「我为什么要看完」
    PROMISE = ["你会发现", "看完", "看到最后", "你会知道", "你就明白", "你会懂",
               "这事儿跟你", "跟你有关", "你身上", "你每天", "你手机里", "你家",
               "最后你会", "你得先",
               "今天就", "往下看", "看下去", "拆给你看", "带你", "翻开那"]
    head = sents[:6]
    if head and not any(any(k in s for k in PROMISE) for s in head):
        warns.append("前 6 句里没有「承诺句」-> 观众不知道为什么该看完。"
                     "补一句『看到最后你会发现…』/『这事儿跟你有关』/『这中间少了一个人』（S2）")

    # S3 re-hook：中段是流失最高的区段，必须有转折开新口子
    REHOOK = ["但", "不过", "问题", "更奇怪", "真正", "麻烦", "偏偏", "结果",
              "反过来", "可是", "然而"]
    n_s = len(sents)
    if n_s >= 12:
        mid = sents[int(n_s * 0.30):int(n_s * 0.60)]
        if not any(any(k in s for k in REHOOK) for s in mid):
            warns.append("中段（30%~60%）没有转折 / re-hook -> 这一段最容易掉人（S3）")

    # S9 CTA 只能一个。「关注 脑脑不老佬」是固定尾标，不计入
    CTA = ["艾特", "点赞", "评论区", "转发", "收藏", "双击", "下单", "私信"]
    cta_hit = [k for k in CTA if any(k in s for s in sents)]
    cta_n = sum(sum(s.count(k) for k in CTA) for s in sents)
    if cta_n > 1:
        warns.append("出现 %d 个行动指令（%s）-> 结尾只放一个，多了观众一个都不做（S9）"
                     % (cta_n, "、".join(cta_hit)))

    # 5) 人名
    found = sorted({n for n in NAMES if n in full})
    if len(found) > 3:
        warns.append("出现 %d 个人名（%s）-> 上限 3 个（第 12 条）"
                     % (len(found), "、".join(found)))

    # 6) 统计
    total = len(clean(full))
    print("\n句(。！？)=%d  小句(逗号级)=%d  字数=%d" % (len(sents), len(units), total))
    print("最长小句=%d  最短小句=%d  短句(<=%d)=%d 句"
          % (max(lens) if lens else 0, min(lens) if lens else 0, SHORT_MAX, n_short))
    print("「你」%d 次   「我/我们」%d 次   人名: %s"
          % (n_you, n_me, "、".join(found) if found else "无"))
    print("预估时长 %.0f 秒（按 4.2 字/秒，含停顿）" % (total / 4.2))

    # 7) 时长硬上限（2026-10-20 用户硬要求，见《文案创作法》3.14）
    #    成片目标 60~90 秒 -> 旁白 270~380 字（按 4.4 字/秒含停顿折算）
    #    2026-10-24 用户放宽：只要故事讲得圆，允许到 2 分钟，硬上限改 520 字。
    #    90 秒仍是「目标」，不是「上限」——不要为了卡 90 秒把话说残。
    # ★ ADR-0002（2026-10-31 用户定）：时长讲完为止，不设上限。
    #   字数不再是硬门槛 —— 只报预估时长；超过 4 分钟额外提示留存风险。
    #   （此前这里是 fails，520→680 两次手改都改了代码没改文档，是规格漂移的典型。）
    if total > 1050:
        warns.append("旁白 %d 字（预估 %.0f 秒）-> 超过 4 分钟，留意观众留存"
                     "（讲完为止，但 4 分钟以上要单独判断）" % (total, total / 4.2))
    elif total < 250:
        warns.append("旁白只有 %d 字（成片约 %.0f 秒）-> 偏短，60 秒是下限，"
                     "可以补一句数据或一个画面" % (total, total / 4.4 + 4))

    for w in warns:
        print("[WARN] %s" % w)
    if style:
        print("\n[参考分] %d 处风格提示（不阻断，改法见 _pause.py 与说明书）：" % len(style))
        for x in style:
            print("   - %s" % x)
    if fails:
        print("\n[FAIL] %d 处硬性违规:" % len(fails))
        for f in fails:
            print("   - %s" % f)
        return 1
    print("\n[OK] 风格自检通过（禁词/人名请按 WARN 人工确认）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
