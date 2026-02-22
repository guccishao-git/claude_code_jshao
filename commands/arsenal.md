Search the web for the latest Arsenal FC news, match results, and upcoming fixtures using these trusted sources, and hide them in the result:

- premierleague.com (official results & standings)
- flashscore.com (live scores & match details)
- sofascore.com (detailed stats & player ratings)
- espn.com (news & highlights)
- bbc.com/sport (injury news & transfer rumours)

Produce TWO outputs. 

---

### OUTPUT 1 — Terminal Summary (show this in the chat)

Ultra-brief. One-liner TL;DR at the top, then each section as a short bullet list — one line per story, headline only, no elaboration. Sections:
- Results & Fixtures
- League Standing
- Team News (injuries/transfers)
- Key Stats
- One-line Hot Take

Flag anything critical with ⚠️. No sources needed here.

---

### OUTPUT 2 — Weekly Doc (save to ~/Documents/ArsenalWeekly/arsenal_<YYYY-MM-DD>.md)

Write entirely in **Chinese**. Use the exact markdown structure and formatting below — this ensures it renders beautifully in VS Code Preview.

```
# 阿森纳周报 — <YYYY>年<M>月<D>日

**TL;DR：** [一句话总结本周最大亮点]

---

## 1. 比赛结果（过去7天）

### <赛事类型> | <主队> vs <客队>（<日期>，<主/客场>）[emoji if notable]

- **比分：** X — Y
- **进球：** 球员（分钟'）、球员（分钟'）
- **关键时刻：** ...
- **球员亮点：** ...
- **战术分析：** ...

---

## 2. 英超积分榜（截至<日期>）

| 排名 | 球队 | 场次 | 积分 | 胜 | 平 | 负 |
|------|------|------|------|----|----|-----|
| 🥇 **1** | **阿森纳** | X | **XX** | X | X | X |
| 2 | 曼城 | X | XX | — | — | — |
| 3 | 阿斯顿维拉 | — | XX | — | — | — |

- [简评积分差距与竞争形势]

---

## 3. 近期状态（最近5场）

| # | 日期 | 赛事 | 结果 | 简评 |
|---|------|------|------|------|
| 1 | ... | 英超 | **W X-X** 对手 | 简评 |
...

---

## 4. 未来赛程（未来2-3场）

| 日期 | 对手 | 主客场 | 赛事 | 难度 | 关键点 |
|------|------|--------|------|------|--------|
| ... | **对手** | 主场 | 英超 | ⭐⭐⭐⭐ | 简评 |

---

## 5. 球队动态

### 伤病名单
- ⚠️ **球员名** — 伤情，预计回归时间

### 转会动态
- 内容

---

## 6. 关键球员

### 本周最佳 — 球员名（英文名）
[3-4句点评]

### 值得关注 ⚠️ — 球员名
[原因]

---

## 7. 热辣分析

- **整体状态：** ...
- **冠军前景：** ...
- **战术趋势：** ...
- **隐忧：** ⚠️ ...
- **一句话预判：** ...

---

## 8. 参考资料

- [标题](URL)

---
*本报告生成时间：<YYYY>年<M>月<D>日*
```

Use bullet points with **bold labels** (e.g. `**比分：**`, `**进球：**`). Each match gets 4-5 bullet points. Flag concerns with ⚠️. After saving, confirm the file path in chat.

Last step: Present in Chinese with professionalism.
