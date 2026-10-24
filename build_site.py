# -*- coding: utf-8 -*-
"""
build_site.py — 把 writeups/*.md 构建成 docs/ 下的零依赖静态站点
用法:  py -3 build_site.py   (在仓库根目录运行)
覆盖的 Markdown 构造: 标题/水平线/围栏代码块/表格/引用/有序无序列表/段落/
                      行内代码/加粗/链接。先做 HTML 转义再变换，保证 <REDACTED_*> 可见。
"""
import html
import os
import re
import shutil

ROOT = os.path.dirname(os.path.abspath(__file__))
WU = os.path.join(ROOT, "writeups")
DOCS = os.path.join(ROOT, "docs")
EVID = os.path.join(ROOT, "evidence")
CERT = "https://www.wiz.io/bug-bounty-masterclass/certificate/43a82202-6aaa-4a0b-b43a-118f380d8af1"

# 每题元数据: 文件序号 -> (短标题, 漏洞类型, 净耗时)
META = {
    "00": ("方法论总纲", "人机协作 / 流程", "—"),
    "01": ("暴露的数据库", "暴露服务 / 无认证", "~15 min"),
    "02": ("航空数据泄露", "证书泄露 / IDOR", "~35 min"),
    "03": ("目录列表暴露", "配置错误", "~10 min"),
    "04": ("工单存储型 XSS", "注入 / 转义不一致", "~15 min"),
    "05": ("域名接管", "悬挂 DNS / S3", "~30 sec"),
    "06": ("SSRF", "SSRF / 凭据泄露", "~10 min"),
    "07": ("GitHub OSINT", "凭据泄露 / git 历史", "~40 min"),
    "08": ("堆转储暴露", "Actuator / 取证", "~50 min"),
    "09": ("0-Click ATO", "会话混淆", "~15 min"),
}

def inline(s: str) -> str:
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s

def md2html(md: str) -> str:
    lines = md.replace("\r\n", "\n").split("\n")
    # 1) 围栏代码块先抽出为占位符
    fences, src, buf, lang, in_fence = [], [], [], "", False
    for ln in lines:
        m = re.match(r"^```(\w*)\s*$", ln)
        if m and not in_fence:
            in_fence, lang, buf = True, m.group(1), []
        elif ln.strip() == "```" and in_fence:
            in_fence = False
            src.append(("@@F%d@@" % len(fences), False))
            fences.append((lang, buf[:]))
        elif in_fence:
            buf.append(ln)
        else:
            src.append((ln, True))
    # 2) 逐块解析
    out, i = [], 0
    while i < len(src):
        raw = src[i][0]
        m = re.match(r"^@@F(\d+)@@$", raw)
        if m:
            lg, code = fences[int(m.group(1))]
            out.append('<pre class="code%s"><code>%s</code></pre>'
                       % (" " + lg if lg else "", html.escape("\n".join(code), quote=False)))
            i += 1
        elif re.match(r"^#{1,6}\s+", raw):
            lvl = len(raw) - len(raw.lstrip("#"))
            out.append("<h%d>%s</h%d>" % (lvl, inline(raw.lstrip("#").strip()), lvl))
            i += 1
        elif re.match(r"^-{3,}\s*$", raw):
            out.append("<hr>")
            i += 1
        elif raw.startswith("|"):
            block = []
            while i < len(src) and src[i][0].startswith("|"):
                block.append(src[i][0]); i += 1
            rows = [r for r in block if not re.match(r"^[\s|:\-]+$", r.replace("|", "", 1))]
            t = ["<table><thead><tr>"]
            heads = [c.strip() for c in rows[0].strip().strip("|").split("|")]
            t += ["<th>%s</th>" % inline(h) for h in heads]
            t.append("</tr></thead><tbody>")
            for r in rows[1:]:
                cells = [c.strip() for c in r.strip().strip("|").split("|")]
                for k in range(len(heads)):
                    t.append("<td>%s</td>" % inline(cells[k]) if k < len(cells) else "<td></td>")
                t.append("</tr><tr>")
            t.append("</tr></tbody></table>")
            joined = "".join(t).replace("<tr></tr></tbody>", "</tbody>")
            out.append(joined.replace("<tbody><tr></tbody>", "<tbody>"))
        elif raw.startswith(">"):
            q = []
            while i < len(src) and src[i][0].startswith(">"):
                q.append(src[i][0].lstrip(">").strip()); i += 1
            out.append("<blockquote><p>%s</p></blockquote>" % "<br>".join(inline(x) for x in q if x))
        elif re.match(r"^[-*]\s+", raw):
            items = []
            while i < len(src) and re.match(r"^[-*]\s+", src[i][0]):
                items.append(re.sub(r"^[-*]\s+", "", src[i][0])); i += 1
            out.append("<ul>" + "".join("<li>%s</li>" % inline(x) for x in items) + "</ul>")
        elif re.match(r"^\d+[.)]\s+", raw):
            items = []
            while i < len(src) and re.match(r"^\d+[.)]\s+", src[i][0]):
                items.append(re.sub(r"^\d+[.)]\s+", "", src[i][0])); i += 1
            out.append("<ol>" + "".join("<li>%s</li>" % inline(x) for x in items) + "</ol>")
        elif raw.strip() == "":
            i += 1
        else:
            para = []
            while i < len(src) and src[i][0].strip() and not re.match(
                    r"^(#{1,6}\s|[-*]\s|\d+[.)]\s|>|\||-{3,}\s*$|@@F\d+@@)", src[i][0]):
                para.append(src[i][0]); i += 1
            out.append("<p>%s</p>" % "<br>".join(inline(x) for x in para))
    return "\n".join(out)

STYLE = """/* Wiz Masterclass 复盘站点 · 深色技术风 */
:root{--bg:#0d1117;--card:#161b22;--line:#30363d;--fg:#c9d1d9;--dim:#8b949e;--acc:#58a6ff;--ok:#3fb950}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.75 -apple-system,"Segoe UI","Microsoft YaHei",sans-serif}
a{color:var(--acc);text-decoration:none}a:hover{text-decoration:underline}
code{background:#1f2937;border:1px solid var(--line);border-radius:4px;padding:1px 6px;font:0.9em/1.6 Consolas,"Courier New",monospace;color:#79c0ff}
pre.code{background:#0a0d12;border:1px solid var(--line);border-radius:8px;padding:14px 16px;overflow-x:auto}
pre.code code{background:none;border:none;padding:0;color:#a5d6ff;font-size:0.88em;line-height:1.6}
header{position:sticky;top:0;z-index:9;background:rgba(13,17,23,.92);backdrop-filter:blur(6px);border-bottom:1px solid var(--line)}
nav{max-width:960px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:16px}
.crumb{color:var(--dim);font-size:13px;flex:1}
.pager{display:flex;gap:12px;font-size:14px}
main{max-width:960px;margin:0 auto;padding:28px 20px 60px}
article h1{font-size:1.9em;line-height:1.35;margin:.2em 0 .4em;color:#f0f6fc}
article h2{font-size:1.35em;margin-top:2em;border-bottom:1px solid var(--line);padding-bottom:.3em;color:#e6edf3}
article h3{font-size:1.12em;margin-top:1.6em;color:#e6edf3}
blockquote{margin:1em 0;padding:.4em 1em;border-left:3px solid var(--acc);background:var(--card);border-radius:0 8px 8px 0;color:var(--dim)}
blockquote p{margin:.4em 0}
table{border-collapse:collapse;width:100%;margin:1em 0;font-size:0.94em;display:block;overflow-x:auto}
th,td{border:1px solid var(--line);padding:7px 11px;text-align:left;vertical-align:top}
th{background:var(--card)}
hr{border:none;border-top:1px solid var(--line);margin:2.2em 0}
footer{border-top:1px solid var(--line);color:var(--dim);font-size:13px;text-align:center;padding:22px}
/* 首页 */
.hero{padding:56px 0 36px;text-align:center}
.hero h1{font-size:2.3em;margin:0 0 12px;color:#f0f6fc}
.hero p{color:var(--dim);max-width:640px;margin:0 auto}
.stats{display:flex;flex-wrap:wrap;gap:14px;justify-content:center;margin:34px 0 10px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 26px;min-width:130px}
.stat b{display:block;font-size:1.5em;color:var(--ok)}
.stat span{color:var(--dim);font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px;margin-top:26px}
.card{display:block;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px 18px;transition:border-color .2s}
.card:hover{border-color:var(--acc);text-decoration:none}
.card .n{color:var(--dim);font-size:12px}
.card .t{font-size:1.06em;margin:2px 0 6px;color:#f0f6fc}
.card .m{color:var(--dim);font-size:13px}
.card .m b{color:var(--acc);font-weight:600}
@media print{body{background:#fff;color:#111}pre.code,th{background:#f6f8fa}}"""

def page(title: str, body: str, pager: str = "") -> str:
    return """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s · Wiz Masterclass 通关复盘</title><link rel="stylesheet" href="style.css">
</head><body><header><nav>
<a href="index.html">← 总览</a><span class="crumb">Wiz Bug Bounty Masterclass · 9/9 · GLM Agent 协作复盘</span>
<div class="pager">%s</div></nav></header>
<main>%s</main>
<footer>基于 GLM 驱动的 Agent 协作完成（2026-10-24）· <a href="%s" target="_blank" rel="noopener">官方证书</a> · 全部敏感内容已脱敏（见仓库 REDACTION.md）</footer>
</body></html>""" % (html.escape(title), pager, body, CERT)

def main():
    os.makedirs(os.path.join(DOCS, "evidence"), exist_ok=True)
    with open(os.path.join(DOCS, "style.css"), "w", encoding="utf-8") as f:
        f.write(STYLE)
    files = sorted(f for f in os.listdir(WU) if f.endswith(".md"))
    pages = []  # (num, title, body)
    for fn in files:
        num = fn.split("-")[0]
        md = open(os.path.join(WU, fn), encoding="utf-8").read()
        title = next(l.lstrip("# ").strip() for l in md.splitlines() if l.startswith("# "))
        pages.append((num, title, md2html(md)))
    # 各题页面 + 前后导航
    for idx, (num, title, body) in enumerate(pages):
        prev_ = pages[idx - 1] if idx > 0 else None
        next_ = pages[idx + 1] if idx < len(pages) - 1 else None
        pager = (('<a href="wu-%s.html">← %s</a>' % (prev_[0], META.get(prev_[0], (prev_[1],))[0])) if prev_ else "") \
              + (('<a href="wu-%s.html">%s →</a>' % (next_[0], META.get(next_[0], (next_[1],))[0])) if next_ else "")
        with open(os.path.join(DOCS, "wu-%s.html" % num), "w", encoding="utf-8") as f:
            f.write(page(title, "<article>%s</article>" % body, pager))
    # 首页
    cards = []
    for num, title, _ in pages:
        short, cls, t = META.get(num, (title, "", ""))
        cards.append('<a class="card" href="wu-%s.html"><div class="n">%s · %s</div>'
                     '<div class="t">%s</div><div class="m">%s　<b>%s</b></div></a>'
                     % (num, num, short, title, cls, t))
    body = """<div class="hero"><h1>一个安全新生与 GLM Agent 的 9/9</h1>
<p>一个下午通关 Wiz Bug Bounty Masterclass 全部九道实操挑战（对应真实赏金合计 $93,300+）。
凭据归人，自动化归 Agent —— 这里是全过程的第一人称复盘。</p></div>
<div class="stats">
<div class="stat"><b>9 / 9</b><span>通关</span></div>
<div class="stat"><b>≈4.5h</b><span>净耗时</span></div>
<div class="stat"><b>$93,300+</b><span>对应真实赏金</span></div>
<div class="stat"><b>80%%</b><span>技术环节由 Agent 执行</span></div>
</div>
<div class="grid">%s</div>""" % "".join(cards)
    with open(os.path.join(DOCS, "index.html"), "w", encoding="utf-8") as f:
        f.write(page("总览", body))
    # 证据图
    n = 0
    for img in os.listdir(EVID):
        if img.lower().endswith((".png", ".jpg", ".jpeg")):
            shutil.copy2(os.path.join(EVID, img), os.path.join(DOCS, "evidence", img)); n += 1
    print("OK: %d 个页面 + style.css + %d 张证据图 → docs/" % (len(pages) + 1, n))

if __name__ == "__main__":
    main()
