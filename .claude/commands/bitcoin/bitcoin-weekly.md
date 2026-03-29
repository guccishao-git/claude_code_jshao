生成本周比特币周报幻灯片，并发布到 GitHub Pages。**所有输出使用中文（简体）。**

## 步骤

### 1. 网络抓取本周最新数据

**直接从网络搜索以下内容，不依赖本地历史数据：**

使用 web_search 搜索以下关键词（中英文各一组）：
- `Bitcoin price today 2026` — 获取当前价格、24h/7d 涨跌幅
- `Bitcoin weekly news this week` — 本周重大事件（ETF、监管、机构动向）
- `Bitcoin price prediction next week` — 短期（1周/1月）机构预测
- `Bitcoin price forecast 2026 year end` — 年底目标价
- `比特币本周行情` — 中文视角补充

从搜索结果中提取并整理：
- 当前价格（USD）
- 本周涨跌幅（%）
- 最重要的 4 条新闻（标题 + 摘要）
- 1周、1月、年底预测价格区间
- 市场情绪（Fear & Greed 或主观判断）

**将以上数据写入今日摘要文件** `~/Documents/BitCoinNewsDaily/digest-YYYY-MM-DD.md`，格式与现有文件一致（含价格表格、新闻、预测、白话总结各节）。

### 2. 参考历史每日摘要（补充上下文）

读取 `~/Documents/BitCoinNewsDaily/` 中最近 7 天的摘要文件，作为辅助参考：
- 补充历史价格走势
- 对比本周与上周的新闻主题变化
- 如有连续趋势（如连续下跌/反弹），在周报中体现

### 3. 运行周报脚本

```
~/Documents/BitCoinNewsDaily/.venv/bin/python3 ~/Documents/GitHub1/claude_code_jshao/scripts/bitcoin_weekly_slides.py
```

脚本自动完成：
- 读取步骤 1 写入的今日摘要 + 步骤 2 的历史摘要文件
- 从 CoinGecko 拉取 1 年历史价格数据
- 生成 6 页霓虹赛博风格幻灯片（含交互式走势图）
- 保存本地副本至 `~/Documents/BitCoinNewsDaily/bitcoin-weekly-YYYY-Www.html`
- 复制到 `docs/bitcoin-weekly.html` 并推送至 GitHub Pages
- 在浏览器中自动打开本地预览

### 3. 终端输出（简短摘要）

脚本成功后打印：

```
📊 W{周数} 比特币周报已生成
   本周走势：{开盘价} → {收盘价}（{周涨跌幅}%）
   关键事件：{本周最重要的一句话新闻}
   在线地址：https://guccishao-git.github.io/claude_code_jshao/bitcoin-weekly.html
```

---

## 幻灯片内容结构（6 页）

| 页码 | 标题 | 内容 |
|------|------|------|
| 1 | 封面 | 周数、日期范围、开/收盘价、周涨跌幅 |
| 2 | 价格走势图 | Chart.js 交互图表，含 1W / 1M / 1Y 时间轴切换、CoinGecko 实价线、摘要标记点、预测中位数虚线 |
| 3 | 价格回顾 | 每日价格与涨跌幅表格 |
| 4 | 市场新闻 | 本周重点事件（最多 4 条） |
| 5 | 预测展望 | 1周 / 1月 / 年底目标价（三栏卡片） |
| 6 | 白话总结 | 本周一句话总结与操作提示 |

---

## 设计规范（霓虹赛博主题）

所有未来报告均沿用以下风格，**不得随意更改**：

| 元素 | 规格 |
|------|------|
| 背景色 | `#050a14` (深海军蓝) |
| 主色调 | `#00ffc8` (青色) |
| 强调色 | `#ff00b4` (品红) / `#ffb340` (琥珀) |
| 危险色 | `#ff5060` (红色) |
| 字体 | Space Grotesk (标题) + Space Mono (数据/代码) |
| 排版 | `clamp()` 响应式字号，全屏滚动吸附 (`scroll-snap`) |
| 图表 | Chart.js 4.x CDN，深色背景，青色网格线 |
| 动画 | `fadeUp` reveal，`driftA/B` 光晕漂移，`gridPulse` 背景格 |

---

## 关键文件路径

| 文件 | 说明 |
|------|------|
| `scripts/bitcoin_weekly_slides.py` | 主生成脚本 |
| `docs/bitcoin-weekly.html` | GitHub Pages 发布页 |
| `~/Documents/BitCoinNewsDaily/bitcoin-weekly-YYYY-Www.html` | 本地存档 |
| `~/Documents/BitCoinNewsDaily/.venv/` | Python 虚拟环境（含 requests、plotly） |
