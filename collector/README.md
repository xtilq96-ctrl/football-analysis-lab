# 中国体彩足球采集器

这是部署在中国大陆云服务器上的后台采集程序。它直接读取中国体育彩票官方胜平负、让球胜平负接口，每五分钟执行一次。

## 已实现

- 官方接口失败自动重试
- SQLite 保存当前比赛、赔率变动历史和每次运行结果
- 已开赛比赛不会因为从官方在售列表消失而被删除
- 同时出现多个销售日时按销售日完整保留，不会互相覆盖
- 原始响应压缩留存 90 天，便于复核
- 生成 `latest.json` 和 `health.json`
- systemd 开机自启、定时执行、阻止重复运行
- 只读数据接口使用 HMAC-SHA256 签名，网站会拒绝伪造或过期数据
- V1 自动计算胜平负、期望进球、比分前五、总进球和大小 2.5 概率
- 每个销售日自动生成最多三组 2 串 1；没有达到门槛时不推荐
- 不需要 API-Football 密钥，不在 GitHub 保存任何密码或私钥

## Ubuntu 22.04 安装

在服务器克隆本仓库后执行：

```bash
sudo ./collector/install.sh
```

查看最近运行结果：

```bash
sudo systemctl status football-ai-collector.service
sudo journalctl -u football-ai-collector.service -n 50 --no-pager
sudo cat /var/lib/football-ai/health.json
```

只读接口为 `http://服务器地址/api/latest` 和 `/api/health`。接口内容虽然是公开赛事资料，但网站仍会校验服务器签名，签名密钥不会进入 GitHub 或浏览器。

数据文件位于 `/var/lib/football-ai/`，程序安装在 `/opt/football-ai/collector/`。

## 数据说明

`latest.json` 中的概率来自体彩官方固定奖的隐含概率，并进行了去水处理。它反映市场定价，不代表比赛结果保证，也不是投注建议。

比分与总进球采用市场概率校准的独立泊松模型（`v1-market-poisson`）。当前版本尚未融合首发、伤停、天气和球队近期 xG，因此必须通过长期赛果回测后才能评估真实预测能力。
