# 03 · Domain Registrar Data Exposure —— 忘关的目录列表

> 系列第 3 题 · 对应真实事件：某大型域名注册商暴露客户数据与内部商业文档（原赏金 $5,000）
> · 我的净耗时：约 10 分钟（第 2 题方法论修正后的第一次兑现）

## 题面

> Sometimes the simplest things get overlooked - a forgotten folder, a directory
> left accessible, files that were never meant to see the light of day.
> Your mission: dig around, find what's hiding in plain sight.

靶场地址：`https://<REDACTED_DOMAIN>/`（一个域名注册商的站点）

## 我的判断路径

题面几乎明示了"可浏览的目录"（directory listing）。这类题的正确姿势不是
一个一个路径去点，而是拿一份像样的目录字典**并行爆破**，只盯非 404 的结果。
有了第 2 题的教训，我先花两分钟做了低成本首页侦察确认没有更快的入口，
然后直接上字典。

## 过程

### 1. 首页侦察：一个没有出口的页面

首页 3.5KB，是个身份验证服务的错误页（Okta 风格"User is not assigned to this
application"），**没有任何链接、任何 JavaScript**——没有比这更强的"去扫目录"信号了。

### 2. 并行目录爆破：83 个路径，一次命中

用 shell 后台任务并发探测 83 个常见目录名（admin、backup、uploads、docs、
internal、certificates、whois……），每个请求带 6 秒超时，全程十几秒：

```bash
for p in admin api backup uploads internal certificates customers docs …; do
  (code=$(curl -sk -o /dev/null -w "%{http_code}" \
     "https://<REDACTED_DOMAIN>/$p/")
   echo "$code /$p/" >> scan.txt) &
done; wait
grep -v "^404" scan.txt    # 只看非 404
```

结果只有一个非 404：

```
200 /uploads/
```

### 3. 目录列表开着：nginx autoindex

`/uploads/` 返回完整的目录列表（`Index of /uploads/`），内容两类：

- 31 个 `jira-stats-*.txt`（内部工单统计导出）
- **`shark-db.zip`（1,860 字节）——数据库备份文件**

### 4. 下载、解压、搜索

```bash
curl -o db.zip https://<REDACTED_DOMAIN>/uploads/shark-db.zip
unzip db.zip          # → shark-db.sql
grep -ri "flag" .     # 命中
```

`shark-db.sql` 是生产库备份：`employees` 表结构包含姓名、邮箱、电话、部门、
**工资、社保号（SSN）、家庭住址**字段（数据值已脱敏——这正是题面所说的
"sensitive customer data"）。flag 藏在一条审计记录里：

```
(999, 'SECURITY_AUDIT', 'audit@…', …, 'SECURITY_LOG: {<REDACTED>}', …)
```

## 关键命令

见上文过程内嵌命令——本题的技术含量不在单条命令，在于**用并行把 83 次探测
压缩到十几秒**，以及只对非 404 结果做二次分析的习惯。

## 失败与弯路

无返工。第 2 题教训（先低成本侦察再上字典）在本题直接兑现：
先确认首页无路可走（2 分钟），字典一轮命中（十几秒），全程 10 分钟。

对比数据值得写进任何方法论文档：

| 题 | 主动字典先行 | 被动侦察先行 |
|---|---|---|
| 第 2 题 | 40+ 路径 × 双方法 ≈ 20 分钟无收获 | 证书 SAN 5 分钟命中 |
| 第 3 题 | —— | 83 路径一轮命中，10 分钟通关 |

## 防御视角（如果我是蓝队）

1. Web 根目录永远关闭 autoindex（nginx 默认开，配置里必须显式 `autoindex off`）
2. 备份文件（`*.zip`、`*.sql`、`*.bak`）不允许出现在 Web 可访问路径，
   传输走带鉴权的渠道
3. 部署流水线加一道"Web 根目录文件白名单"检查，非白名单文件不发布
4. 本质上这是配置错误而非代码漏洞——**安全基线检查（CIS Benchmark）能直接拦住这类问题**

## 证据

- `evidence/03-1-flag-submitted.png` —— 提交成功页面
