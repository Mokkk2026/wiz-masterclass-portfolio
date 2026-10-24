# 07 · GitHub Authentication Bypass on Major CRM —— 被删除的 token 与忘不掉的 git 历史

> 系列第 7 题 · 对应真实事件：员工公开仓库泄露凭据导致 CRM 内部系统未授权访问（原赏金 $12,000）
> · 我的净耗时：约 40 分钟 · 全系列唯一一道**必须由人完成关键一步**的题

## 题面

> Developers often reference their work domains in code, configs, and scripts -
> and sometimes those files end up in personal GitHub repositories with more
> than just the domain name.
> Search for "bugbountymasterclass.com" on GitHub and see what you can find.
> Your mission: find what an employee accidentally committed.

靶场地址：`https://<REDACTED_DOMAIN>/`（一个仿 GitHub Enterprise 站点，
登录页附带 "Validate GitHub Token" 验证入口）

## 我的判断路径

题面直接给了 OSINT 方向：在 GitHub 公开代码里搜课程域名。我很快撞上了本题真正的考点：
**GitHub 的代码搜索（唯一能搜到文件内容的入口）必须登录才能使用**。
这决定了本题的作业形态——我和 Agent 必须分工。

## 过程

### 1. Agent 侧：匿名信源全线碰壁（~15 分钟）

我先把所有**不需要凭据**的途径走了一遍，全部落空：

| 途径 | 结果 |
|---|---|
| GitHub API 仓库搜索 / Issue 搜索 / 提交搜索 | `total_count: 0`（这三类搜索不索引文件内容） |
| grep.app（公开代码搜索引擎） | 触发人机验证，无法访问 |
| Sourcegraph 公开搜索 | 空结果 |
| 搜索引擎 site: 查询 | 只索引到课程官方页面和他人的 writeup |

结论明确：**代码搜索的登录态绕不开**。

### 2. 人机握手：登录态操作交给人

我登录自己的 GitHub 账号，在代码搜索里输入课程域名，命中 8 个文件。
关键的一条来自 `nagliwiz/cool-stuff` 仓库——一个 `.env` 文件
（`nagliwiz` 是课程虚构的"员工"账号）。

这一步完成的同时，后续全部交还 Agent。

### 3. Agent 侧：翻 git 历史，挖出"已删除"的凭据

用 GitHub 匿名 API 拉取仓库内容（这里有个环境插曲：`raw.githubusercontent.com`
在本地网络无法解析，改走 `api.github.com` + `Accept: application/vnd.github.raw`
媒体类型拿到文件原文）：

- **当前版本的 `.env`**：只剩一行内部域名 `<REDACTED_DOMAIN>`（解析都不存在的
  剧情装饰），没有凭据
- 但提交历史里有**多次 "Update .env"**——有修改就有故事

调出历史版本，其中一次提交的 `.env` 是：

```
<REDACTED_DOMAIN>
GITHUB_TOKEN=<REDACTED_TOKEN>
```

**凭据曾经提交过，后来从工作区删掉了——但 git 历史里永远都在。**
这是真实世界凭据泄露的第一大来源：`.gitignore` 加晚了，或者"删文件"被当成了"删历史"。

### 4. 验证收尾

把找回的 token 提交到仿企站的验证接口：

```bash
curl -X POST https://<REDACTED_DOMAIN>/api/validate-token \
  -H 'Content-Type: application/json' \
  -d '{"token":"<REDACTED_TOKEN>"}'

→ {"flag": "<REDACTED>", "message": "Token validated successfully!", "success": true}
```

（小插曲：token 字符串末尾带着出题人的花括号注释，整串提交会 401，
剥掉注释后纯 token 才通过——提交前先看清 token 的边界。）

## 人机协作复盘（本题的核心价值）

这题是"凭据归人，自动化归 Agent"协议的完整演绎：

| 环节 | 执行者 | 为什么 |
|---|---|---|
| 匿名信源穷举（API/搜索引擎） | Agent | 无凭据、可并行、结果可验证 |
| **GitHub 登录与代码搜索** | **人** | 登录态是我的资产；Agent 不持有也不应持有我的凭据 |
| 仓库内容/提交历史枚举 | Agent | 匿名 API 即可，纯机械劳动 |
| token 验证与提交 | Agent → 人 | 接口验证交 Agent，最终 flag 在课程页面由人提交 |

事后看，Agent 在第 1 步穷举所有匿名途径的价值不只是排除法——它把"必须动用人的
登录态"这个结论变成了**有证据的决策**，而不是偷懒的推诿。

## 防御视角（如果我是蓝队）

1. **git 历史是泄密黑洞**：泄露过的凭据必须**轮换**（改代码/删文件毫无意义），
   并用 `git filter-repo` / BFG 清理历史（对已公开仓库，轮换是唯一现实解）
2. 部署 pre-commit 密钥扫描（gitleaks / trufflehog 类工具），把 `.env` 类文件挡在提交前
3. 内部系统凭据（本题的 token 能通过企业验证接口）应绑定来源 IP/设备/短有效期，
   即使泄露也难利用
4. 员工个人仓库引用工作域名是常态，蓝队应反过来做：**主动监控公开代码库中
   出现自家域名的提交**（这是防御侧的 OSINT）

## 证据

- `evidence/07-1-flag-submitted.png` —— 提交成功页面
- 含个人 GitHub 账号信息的搜索过程截图按脱敏规范未入库
