# -*- coding: utf-8 -*-
"""一次性把七期 covers.json 改成统一文案口径（本机临时脚本，跑完可删）"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _rw import rewrite

WORK = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "30 制作")

DATA = {
 "NO.17_等一句话": {
   "no": "NO.17", "title": "等一句话", "slug": "等一句话",
   "sub": "红眼岛 · 一百天", "num": "100",
   "cap": "一句废话，两百人下海", "word": "一句",
   "chips": "一句废话|200 人一个没剩", "art": "crowd", "en": ""},
 "NO.18_围一圈报数": {
   "no": "NO.18", "title": "报到就死", "slug": "报到就死",
   "sub": "约瑟夫环 · 数到 3", "num": "25",
   "cap": "25 个人，只活 1 个", "word": "14 号",
   "chips": "25 个人，只活 1 个", "art": "crowd", "en": ""},
 "NO.19_地球加长一米": {
   "no": "NO.19", "title": "十六厘米", "slug": "十六厘米",
   "sub": "赤道绳子 · 加一米", "num": "16",
   "cap": "跟地球多大没关系", "word": "16cm",
   "chips": "跟地球多大没关系", "art": "planet", "en": ""},
 "NO.20_住满的旅馆": {
   "no": "NO.20", "title": "客满了", "slug": "客满了",
   "sub": "希尔伯特旅馆 · 无穷", "num": "∞",
   "cap": "零空房，塞无穷人", "word": "∞ 间",
   "chips": "零空房，塞无穷人", "art": "bed", "en": ""},
 "NO.21_两扇门": {
   "no": "NO.21", "title": "问错就死", "slug": "问错就死",
   "sub": "两个守卫 · 只问一句", "num": "1",
   "cap": "真话假话都指错门", "word": "一句",
   "chips": "真话假话都指错门", "art": "door3", "en": ""},
 "NO.22_少了一格": {
   "no": "NO.22", "title": "多出一格", "slug": "多出一格",
   "sub": "失踪的正方形 · 64 格", "num": "65",
   "cap": "64 格拼成 65 格", "word": "一格",
   "chips": "64 格拼成 65 格", "art": "chart", "en": ""},
 "NO.23_蒙眼分硬币": {
   "no": "NO.23", "title": "蒙眼分钱", "slug": "蒙眼分钱",
   "sub": "不许看 · 不许数", "num": "10",
   "cap": "抓 10 枚全翻面", "word": "7 比 7",
   "chips": "抓 10 枚全翻面", "art": "hand", "en": ""},
}

for d, cfg in DATA.items():
    p = os.path.join(WORK, d, "covers.json")
    txt = json.dumps(cfg, ensure_ascii=False, indent=1) + "\n"
    how = rewrite(p, txt)
    print("%-22s %-8s  %s" % (d, how, cfg["title"]))
