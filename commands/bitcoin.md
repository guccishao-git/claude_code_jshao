Search the web for the current Bitcoin (BTC) price and do the following. **All output must be in Chinese (Simplified).**

## 终端输出（简短）
在终端打印简短的摘要，包含：
1. 当前价格（美元）
2. 24小时涨跌幅（百分比）
3. 一句话市场情绪
4. 下周价格预测

最多3-4行，语气轻松，避免专业术语。

## 每日摘要文件（详细）
将详细摘要写入 `~/Documents/BitCoinNewsDaily/digest-YYYY-MM-DD.md`（使用今天的日期）。包含：

1. 当前价格（美元）
2. 24小时涨跌幅（百分比）
3. 7日和30日表现
4. 近期新闻与市场背景（2-3条）
5. 价格预测：1周、1个月、1年
   - **1周和1个月的预测必须给出单一目标价**（不是区间范围），格式为：目标价 ± 具体金额。例如：$69,500 ± $695。区间宽度不得超过目标价的1%（即 ±0.5%）。
   - 1年预测可保留宽区间（机构共识范围）。
6. 用通俗易懂的语言总结——这一切意味着什么？

使用Markdown格式，标题清晰，语气轻松易读。

## 更新图表
写完摘要文件后，运行以下命令自动更新价格预测图表：

```
~/Documents/BitCoinNewsDaily/.venv/bin/python3 ~/Documents/BitCoinNewsDaily/bitcoin_chart.py
```

运行成功后，图表会自动在浏览器中打开。
