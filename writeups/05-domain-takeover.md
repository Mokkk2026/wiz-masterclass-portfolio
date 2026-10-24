# 05 · Root Domain Takeover on Fintech Company —— 还在服役的 DNS，已经死去的服务

> 系列第 5 题 · 对应真实事件：过期 DNS 记录导致金融科技公司域名被完全接管（原赏金 $2,000）
> · 我的净耗时：约 30 秒（全项目最快）

## 题面

> Their DNS records are pointing somewhere - but is anyone still home?
> When companies migrate services or shut down resources, sometimes the DNS
> sticks around longer than it should.
> Your mission: investigate the DNS, find the unclaimed resource, and claim your flag.

靶场地址：`https://<REDACTED_DOMAIN>/`

## 我的判断路径

子域名/域名接管（subdomain takeover）的侦察有三步定式，我按顺序走：

1. 查 DNS 记录指向（A / CNAME / NS）
2. 访问目标，识别**服务商错误签名**——不同平台的"资源不存在"错误各有特征
   （S3 的 `NoSuchBucket`、Heroku 的 "No such app"、GitHub Pages 的 404 页……）
3. 对照社区维护的接管可行性清单（如 can-i-take-over-xyz 项目）确认可利用性

DNS 类题目侦察成本极低，所以我在排期上把它提到了技术型题目前面。

## 过程（一步到位）

### DNS 三查 + 一次 HTTP 探测

```
nslookup <REDACTED_DOMAIN>            → A 记录指向 <REDACTED_IP>，无 CNAME
nslookup -type=NS <父域>              → Cloudflare 托管 DNS
curl https://<REDACTED_DOMAIN>/       → HTTP 404，返回 AWS S3 风格 XML
```

那个 404 响应体就是全部答案：

```xml
<!-- Flag: <REDACTED> -->
<Error>
  <Code>NoSuchBucket</Code>
  <Message>The specified bucket does not exist</Message>
  <BucketName><REDACTED></BucketName>
  ...
</Error>
```

**DNS 仍然指向一个已经删除的 S3 存储桶。** 真实攻击里，下一步是去 AWS 注册同名桶——
此后该公司域名下所有流量都会加载攻击者控制的内容。这就是题面"claim your flag"
的双关：认领资源，即接管域名。

## 方法论备注

- `NoSuchBucket` 是 S3 接管的标志性错误签名，看一眼就能定性，不需要进一步验证
- 接管类漏洞是典型的**低成本高影响**：发现只要几分钟，报告写作清晰即可拿赏金；
  真实世界里云厂商（AWS/Azure/GCP）和各类 SaaS 都有对应变体

## 失败与弯路

无。按"侦察三步定式"走完全程没有分叉——这也是把方法论规则化的价值：
第 2 题交过学费后，简单题不再有思考成本。

## 防御视角（如果我是蓝队）

1. **服务下线的正确顺序是"先删 DNS，再删资源"**——反过来就制造悬挂记录
2. 定期审计 DNS 记录：逐条确认指向的资源仍然存在且归属自己
   （Cloudflare 等厂商已提供悬挂记录自动检测）
3. 对曾指向云存储/CDN 的记录建立台账，云资源销毁流程必须联动 DNS 清理
4. 监控侧：对自家域名配置错误页监控，`NoSuchBucket` 这类响应出现即告警

## 证据

- `evidence/05-1-flag-submitted.png` —— 提交成功页面
