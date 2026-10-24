# 02 · Major Airline Data Dump —— 一张证书泄露的内部 API

> 系列第 2 题 · 对应真实事件：暴露的 API 导致数千乘客个人信息、订票与行程泄露（原赏金 $3,000）
> · 我的净耗时：约 35 分钟（其中约 20 分钟花在一条后来被证明错误的路上）

## 题面

> You've been given access to a major airline's booking system. Word on the street
> is that the developers left something exposed that reveals more than it should.
> Your mission: explore the target, find what the developers forgot to hide.

靶场地址：`https://<REDACTED_DOMAIN>/`

## 我的判断路径

"developers left something exposed"（开发者忘了藏某样东西）是个宽泛提示，
可能是 `.git`、`.env`、备份文件、API 文档任何一种。我先按惯性走了主动探测的路，
碰壁后才切换到被动侦察——这个顺序问题成了本题最大的教训，也是整个项目的方法论转折点。

## 过程

### 1. 站点侦察：一个纯静态的"壳"

首页 6.9KB，"航空公司订票站"，但细看不对劲：**没有任何 JavaScript**，
搜索表单没有提交逻辑，导航全是页内锚点。响应头暴露 `X-Powered-By: Express`。

我由此判断：真正有攻击面的东西不在这个页面里，在别处。

### 2. 弯路：字典爆破先行（~20 分钟，全部落空）

我拿常见敏感路径字典跑了 GET + POST 双方法共 40+ 个路径：
`.git/`、`.env`、`swagger`、`api/`、`admin`、`login`……全部 404。
`OPTIONS /` 返回 `Allow: GET, HEAD`，连方法层面都没留口子。

唯一的非 404 是 `/health`：

```json
{"status":"healthy","service":"nagli-airlines-api"}
```

这确认了背后确实有一个 API 服务在跑——但它不在我猜的任何路径上。

### 3. 转折：被动侦察一击致命

我停掉字典，改为问"**这个域名本身对外暴露了什么信息**"。
第一件事就是看 TLS 证书的 SAN（Subject Alternative Name）字段：

```bash
openssl s_client -connect <REDACTED_DOMAIN>:443 -servername <REDACTED_DOMAIN> </dev/null \
  | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"
```

```
DNS:<REDACTED_DOMAIN>, DNS:api.<REDACTED_DOMAIN>
```

**证书 SAN 里躺着一个从未在任何页面出现过的内部 API 子域名。**
这就是题面说的"忘了藏的东西"——把内部域名签进公开证书，等于免费昭告天下。

顺手又查了 CT 日志（crt.sh，查询 `%.<REDACTED_DOMAIN>`），把全部子域名枚举了一遍——
这一步的收益远超本题：后面 7 道题的靶场域名全部来自这张"战场地图"。

### 4. API 子域：Swagger 文档暴露 + 无认证 IDOR

`api.<REDACTED_DOMAIN>/docs` 返回 Swagger UI，OpenAPI 规范内嵌在
`/docs/swagger-ui-init.js` 里，共 10 个接口，全部围绕 `memberId` 取乘客数据：

```
/api/getBookings       /api/getContactInfo    /api/getFlightHistory
/api/getMembership     /api/getMemberships    /api/getPaymentMethods
/api/searchListMember  /api/searchMemberInfo  /api/updateMemberInfo
/api/updateMergeMemberInfo
```

我逐个无认证调用，发现防御只做了一半：

| 接口 | 无认证结果 |
|---|---|
| `getMemberships` | **200，直接吐出 2 名乘客完整档案**：姓名、邮箱、电话、住址、生日、信用卡后四位 |
| `getMembership?memberId=…` | 200，返回单人口径完整档案 |
| `getFlightHistory` / `getPaymentMethods` / `searchMemberInfo` | 200，行程与支付信息裸奔 |
| `getBookings` / `getContactInfo` | 401，有真正的 token 校验 |

用 `getMemberships` 泄露的真实 memberId（`72041008520`）代入 `getMembership`，
返回的完整 JSON 中就带着 `"flag": "<REDACTED>"` 字段。

（我还顺手试了那两个 401 接口的绕过：`Bearer null`、`Bearer <memberId>`、伪造 Basic 头，
全部失败——说明不是统一的疏忽，而是**部分接口做了校验、部分没做**。）

### 5. 最后一个小坑

前两轮我都只看了响应的前几百字符，flag 藏在 JSON 后半段，差点漏掉。
改为**全量落盘到文件再 `grep -ri` 特征**，立刻命中。

## 关键命令（脱敏后结构可复用）

```bash
# 被动侦察：证书 SAN + CT 日志
openssl s_client -connect <REDACTED_DOMAIN>:443 -servername <REDACTED_DOMAIN> </dev/null \
  | openssl x509 -noout -text | grep -A2 "Subject Alternative Name"

# API 文档与数据
curl https://api.<REDACTED_DOMAIN>/docs/swagger-ui-init.js          # 内嵌 OpenAPI 规范
curl https://api.<REDACTED_DOMAIN>/api/getMemberships               # 无认证 → 乘客档案
curl "https://api.<REDACTED_DOMAIN>/api/getMembership?memberId=72041008520" \
  -o member.json && grep -o '"flag":"[^"]*"' member.json            # 全量落盘再搜
```

## 失败与弯路（本题是全项目最重要的一课）

- **40+ 路径字典 + 双方法探测 ≈ 20 分钟颗粒无收**；而证书 SAN + CT 日志 **5 分钟**
  拿到了本题答案外加后续 7 题的靶场地图。成本收益完全倒挂。
- 从此我把作业顺序规则化：**被动侦察（DNS/证书/CT/指纹）永远先于字典爆破**。
  这个规则在第 3 题立刻兑现（10 分钟速通）。
- 只看响应开头几百字符的习惯差点让我漏掉 flag——证据要全量落盘再搜索。

## 防御视角（如果我是蓝队）

1. 内部域名/服务名永远不进公开证书 SAN；用泛域名证书或按需签发
2. API 文档（Swagger/OpenAPI）生产环境必须下线或鉴权
3. 鉴权要在网关层统一做，而不是每个接口各自为政——本题"一半裸奔一半有锁"就是反面教材
4. 对象级授权（BOLA/IDOR）：memberId 属于可枚举的顺序 ID，应改用不可预测标识 + 归属校验

## 证据

- `evidence/02-1-flag-submitted.png` —— 提交成功页面
