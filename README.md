# 通关 Wiz Bug Bounty Masterclass：一个安全新生与 GLM Agent 的 9/9

> **TL;DR** — I solved all 9 hands-on challenges of the Wiz Bug Bounty Masterclass
> (each based on a real bug bounty finding, $93,300+ combined payouts) in one
> afternoon, working as a two-person team with a GLM-powered agent: the agent did
> recon, exploits and forensics; I held every credential and made every call.
> Official certificate verified at the bottom. Write-ups inside, fully redacted.

## 这是什么

我是网络安全专业大一学生。2026 年 10 月 24 日，我用一个下午（净耗时约 4.5 小时）完成了
[Wiz Bug Bounty Masterclass](https://www.wiz.io/bug-bounty-masterclass) 全部 9 道实操挑战，
获得官方认证证书。

这个仓库是完整复盘：每道题的攻击思路（第一人称 writeup）、方法论、失败模式分析，
以及可验证的成果证据。所有敏感信息已脱敏（见 [REDACTION.md](REDACTION.md)）。

## 为什么值得一看

1. **人机协作协议比自动化本身更有参考价值**——"凭据归人，自动化归 Agent"：
   登录、注册、代码搜索、flag 提交全部由人完成；侦察、编码攻击、爆破、取证分析交给 Agent。
   第 7 题（OSINT）是这个协议的完整演绎。
2. **失败模式全部留痕**——自动翻译污染报错、OCR 误读域名、字典先于被动侦察、
   截断的堆转储上做分析……每条翻车都被规则化，可复用于任何同类项目。
3. **9 道题覆盖 9 类真实漏洞**，从暴露数据库到 0-Click 账户接管。

## 战果总览

| # | 挑战（真实漏洞赏金） | 漏洞类型 | 净耗时 |
|---|---|---|---|
| 1 | Open Deepseek Database（>$1M 损失） | 暴露数据库 | ~15 min |
| 2 | Major Airline Data Dump（$3,000） | 证书泄露 + API 文档暴露 + IDOR | ~35 min |
| 3 | Domain Registrar Data Exposure（$5,000） | 目录列表暴露 | ~10 min |
| 4 | Logistics Admin Panel Compromise（$18,000） | 存储型 XSS | ~15 min |
| 5 | Root Domain Takeover（$2,000） | S3 悬挂 DNS 接管 | ~30 sec |
| 6 | SSRF on Gaming Company（$27,500） | SSRF → 内部凭据泄露 | ~10 min |
| 7 | GitHub Auth Bypass on CRM（$12,000） | 凭据泄露（git 历史） | ~40 min |
| 8 | Breaking into a Major Bank（$4,800） | Actuator 堆转储暴露 | ~50 min |
| 9 | 0-Click ATO via Cookie Switching（$20,000） | 跨环境会话混淆 | ~15 min |

合计对应真实赏金 **$93,300+**。总耗时含约 1 小时的注册链路排障（本身也是一段
值得记录的网络诊断实践，见 writeup 00）。

## 目录

```
writeups/               ← 全部完稿
  00-methodology.md       方法论：Agent 选型、人机分工协议、作业循环、失败模式清单
  01-open-database.md     暴露数据库：端口指纹 → 无认证 ClickHouse → 全表特征搜索
  02-airline-data-dump.md 证书 SAN 泄露内部 API → Swagger 暴露 → 无认证 IDOR
  03-directory-exposure.md 83 路径并行爆破 → 目录列表 → 数据库备份
  04-stored-xss.md        同一数据两种渲染：列表页转义、详情页零转义
  05-domain-takeover.md   悬挂 DNS → S3 NoSuchBucket 接管签名
  06-ssrf.md              fileName 吃完整 URL → 环回访问 → 内部凭据回显
  07-github-osint.md      人机协作样本：git 历史里被"删除"的 token
  08-actuator-heapdump.md 最深一课：截断的堆转储与证据完整性
  09-session-confusion.md 压轴：双环境共享签名密钥的 0-Click ATO
evidence/               脱敏后截图（9 张，随各题 writeup 引用）
docs/                   静态站点（零依赖纯 HTML，GitHub Pages 从本目录发布）
build_site.py           站点构建脚本：writeups/*.md → docs/（py -3 build_site.py）
gen_pdf.py              PDF 构建脚本：writeups/*.md → 29 页排版复盘报告
Wiz-Masterclass-通关复盘.pdf   成品 PDF（封面 + 目录 + 总览 + 十章 + 附录）
```

## 可验证凭证

- 官方证书（平台公开分享链接）：
  https://www.wiz.io/bug-bounty-masterclass/certificate/43a82202-6aaa-4a0b-b43a-118f380d8af1
- 仓库地址：【待我确认：GitHub 用户名与仓库名，阶段 7 发布时回填】

## 脱敏声明

所有 flag、token、cookie、密钥、个人邮箱、服务器 IP 以 `<REDACTED_*>` 形式呈现；
靶场域名在文字中脱敏为 `<REDACTED_DOMAIN>`（截图中的靶场域名视为课程公开信息保留）。
请求结构、参数名、状态码、工具与命令全部保留，保证可复现性。
详见 [REDACTION.md](REDACTION.md)。

---

*Built with a GLM-powered agent (ZCode) · 2026-10-24*
