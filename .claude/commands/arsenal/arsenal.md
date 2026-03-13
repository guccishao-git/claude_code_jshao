Search the web for the latest Arsenal FC news, match results, and upcoming fixtures using these trusted sources, and hide them in the result:

- premierleague.com/tables (official standings — use this specific URL for the full table)
- bbc.com/sport/football/premier-league/table (cross-check standings, especially games played)
- flashscore.com (live scores & match details)
- sofascore.com (detailed stats & player ratings)
- espn.com (news & highlights)
- bbc.com/sport (injury news & transfer rumours)

**Before producing any output, verify ALL statistics using the checklist below. Never infer, estimate, or hallucinate — only use confirmed figures. If a stat can only be found from one source, mark it "(待核实)" in the output.**

**① Match Results & Goalscorers**
- Confirm final score from at least 2 sources (e.g. flashscore.com + espn.com or bbc.com/sport)
- Confirm each goalscorer name, minute, and type (open play / penalty / OG) from at least 2 sources
- Confirm red cards, assist credits, and key events from match reports — do not guess

**② Premier League Standings**
- Fetch the full table from premierleague.com/tables
- Cross-check games played (P), W, D, L for Arsenal AND the current 2nd-place team against a second source (espn.com or bbc.com/sport/football/premier-league/table)
- Sanity check: Played must equal W + D + L for every team shown — if numbers don't add up, re-fetch and correct before continuing
- Never infer or estimate match counts — only use confirmed figures from at least two sources

**③ Form Table (Last 5)**
- Verify each of Arsenal's last 5 results (opponent, score, W/D/L) from flashscore.com or sofascore.com
- Do not reconstruct form from season aggregate stats — use the actual match list

**④ Injury & Suspension List**
- Use at least one official or specialist source (arsenal.com, physioroom.com, bbc.com/sport, or 3addedminutes.com)
- Note expected return timeline only if a source explicitly states it — otherwise write "待定"
- Flag suspended players separately from injured players

**⑤ Title Race Rival Stats**
- Verify rival's W, D, L, GD, and points with the same P = W + D + L sanity check
- Confirm rival's last 3 results from flashscore.com or sofascore.com — include scores, not just W/D/L
- Confirm rival's upcoming fixtures from their official club site or premierleague.com

**⑥ Upcoming Arsenal Fixtures**
- Verify dates, opponents, and competition from arsenal.com/fixtures or premierleague.com
- Do not infer fixture dates from memory — fetch them

Produce FOUR outputs.

---

### OUTPUT 1 — Terminal Summary (show this in the chat)

Ultra-brief. One-liner TL;DR at the top, then each section as a short bullet list — one line per story, headline only, no elaboration. Sections:
- Results & Fixtures (include UK time + New Zealand time for upcoming matches)
- League Standing (verify games played for all teams shown from premierleague.com/tables before displaying)
- Team News (injuries/transfers)
- Key Stats
- One-line Hot Take
- **Title Race Rival** — current 2nd place team, points gap, last result, next fixture, and one line on whether it affects Arsenal's title chances

Flag anything critical with ⚠️. No sources needed here.

Then show the **Starting XI Lineup Diagram** for the most recent match (or confirmed upcoming lineup if available). Render it as an ASCII pitch like professional football media — top of pitch = attacking end, bottom = goalkeeper. Show formation name above the diagram (e.g. `4-3-3`). Each player shown as `#N  Name` positioned on the pitch in their approximate row. Use box-drawing characters for the pitch outline and centre circle. Example style:

```
         4-3-3

┌─────────────────────────────┐
│                             │
│  #11 Martinelli  #9 Havertz  #7 Saka  │
│                             │
│    #8 Ødegaard              │
│  #35 Zinchenko  #29 Rice  #41 Merino  │
│                             │
│ #35 Timber  #6 Gabriel  #12 Saliba  #2 Ben White │
│                             │
│           #22 Raya          │
└─────────────────────────────┘
```

Adjust spacing so names are roughly evenly spread across each row. Label the diagram with match info (opponent, date, competition) above it.

---

### OUTPUT 2 — Weekly Doc (save to ~/Documents/ArsenalWeekly/arsenal-<YYYY-MM-DD>.md)

Full write-up with the following sections:
1. **Match Results** (last 7 days) — score, competition, key moments, player standouts, tactical notes
2. **Starting XI** — for the most recent match only, show the confirmed lineup as an ASCII pitch diagram with formation, player names, and shirt numbers (same style as Output 1). Include substitutes listed below the pitch.
3. **Premier League Standing** — Pull full table from premierleague.com/tables. Cross-check games played for Arsenal and rival team against BBC Sport table. Confirm P = W + D + L before displaying. Show current position, points, GD, gap to top/rivals, form table.
4. **Upcoming Fixtures** (next 2-3 matches) — opponent, date, competition, difficulty rating, what's at stake. Always include both **UK time (GMT/BST)** and **New Zealand time (NZDT/NZST)** for each fixture. Note any upcoming clock changes (UK clocks spring forward last Sunday of March; NZ clocks fall back first Sunday of April).
5. **Recent Form** (last 5 matches) — W/D/L breakdown with brief context per match
6. **Team News** — injuries (player, issue, return estimate), transfers, suspensions, notable squad updates
7. **Title Race Rival** — identify the current 2nd-place team and provide:
   - Recent form: last 3 results with scores
   - Upcoming fixtures (next 2-3 matches) — opponent, date, difficulty
   - Points gap to Arsenal and games in hand/deficit
   - Brief analysis: does their schedule help or hurt Arsenal's title chances? Any banana skins coming up for them?
8. **Key Players** — top scorer, best performer of the week, player of concern
9. **Hot Takes** — analysis of how Arsenal are performing, title race outlook, critical upcoming matches, tactical trends worth watching
10. **Sources** — all referenced articles linked at the bottom

Each story 4-5 sentences. Use bullet points. TL;DR one-liner at the very top. Highlight action items or concerns with ⚠️. After saving, confirm the file path in chat.

Last step: Present in Chinese with a sense of professionalism.

---

### OUTPUT 3 — Lineup Graphic (save to ~/Documents/ArsenalWeekly/arsenal-<YYYY-MM-DD>-lineup.html)

Generate a self-contained HTML file that renders a professional-looking football pitch lineup card for the most recent match. Open it in the browser — it should look like something from BBC Sport or Sky Sports.

**Design requirements:**

- Full-page dark background (`#1a1a2e`)
- Centered card layout, max-width 600px
- **Header**: Both team logos side-by-side flanking the score — use Premier League CDN badge URLs (`https://resources.premierleague.com/premierleague/badges/100/t<ID>.png`, Arsenal = t3, Tottenham = t6, Liverpool = t14, Man City = t43, Chelsea = t8, Man Utd = t1, etc.). Include emoji fallback via `onerror`. Team names below each logo. Score in the centre. White text on Arsenal red (`#EF0107`)
- **Pitch**: Deep green gradient background (`#2d5a27` to `#1e3d1a`), white pitch markings (centre circle, halfway line, penalty arcs, goal boxes) drawn with CSS borders and border-radius
- **Players**: Each player rendered as a white circle (50px diameter) with their shirt number in bold Arsenal red inside, and their name in small white text below the circle. Circles are absolutely positioned in rows according to their formation line (attackers at top of pitch, goalkeeper at bottom)
- **Formation label**: Shown in white above the pitch (e.g. `4-3-3`)
- **Substitutes bench**: Listed below the pitch in a clean row of smaller grey circles with names
- **Footer**: Match score and scorers if available

Use inline CSS only (no external dependencies). Position players using flexbox rows stacked vertically inside the pitch div. Each formation line = one flex row, spaced evenly. The pitch should be approximately 560px wide × 750px tall.

After saving, confirm the file path and remind the user to open it in a browser. Also run: `open ~/Documents/ArsenalWeekly/arsenal-<YYYY-MM-DD>-lineup.html` to auto-open it.

---

### OUTPUT 4 — Weekly Slides (save to ~/Documents/ArsenalWeekly/arsenal-<YYYY-MM-DD>-slides.html)

Generate a self-contained, full-screen scroll-snap HTML slide deck summarising the week in Arsenal. Use the **Stadium Lights theme** — match the existing design style exactly as used in `arsenal-feb2026-slides.html`.

**Design theme — Stadium Lights (preserve exactly):**

| Element | Spec |
|---------|------|
| Background | `#080b10` (near-black) |
| Primary | `#EF0107` (Arsenal red) — `--red-dim: rgba(239,1,7,0.15)`, `--red-glow: rgba(239,1,7,0.35)` |
| Gold accent | `#D4AF37` — `--gold-dim: rgba(212,175,55,0.15)` |
| Text | `#f0ede8` / muted `rgba(240,237,232,0.5)` |
| Fonts | Syne 600–800 (display/headings) + Noto Sans SC 300–700 (Chinese body) + Oswald 400–700 (stats/numbers) via Google Fonts |
| Layout | `scroll-snap-type: y mandatory`, each `.slide` = `100vw × 100dvh`, `scroll-snap-align: start` |
| Background FX | `.beams` (4 red light beams swaying from top, `beamSway` keyframe), `.pitch-bg` (subtle grid at bottom 30%), `.center-glow` (radial red gradient from top-center) |
| Crest watermark | Faint Arsenal crest (`opacity: 0.04`) positioned right side on each slide, using `https://resources.premierleague.com/premierleague/badges/100/t3.png` with emoji fallback |
| Typography scale | All `clamp()` — title `clamp(2.2rem, 6vw, 5rem)`, h2 `clamp(1.5rem, 3.5vw, 2.75rem)`, body `clamp(0.78rem, 1.3vw, 1rem)` |
| `.tag` component | Uppercase, letter-spacing 0.25em, red color, preceded by an 18px red line (`::before`) |
| Cards | `background: rgba(255,255,255,0.04)`, `border: 1px solid rgba(239,1,7,0.15)`, `border-radius: 8px` |
| Nav dots | Fixed right-side dot indicator, active dot = red, inactive = muted |
| Animations | `fadeUp` reveal on slide content entry; `beamSway` on light beams |

**Slide structure (6 slides):**

| # | Title | Content |
|---|-------|---------|
| 1 | 封面 (Cover) | Arsenal crest, "阿森纳本周快报", date in Chinese, one-line TL;DR in Chinese |
| 2 | 本周战报 (Match Results) | Last 1-2 results — score, competition, key goalscorers, brief tactical note. Use large score display with Oswald font. |
| 3 | 积分榜 (League Standing) | PL table showing top 5 teams — Arsenal row highlighted with red background tint. Columns: 排名, 球队, 赛, 胜, 平, 负, 净, 积分. W/D/L form pills for last 5 (W=`#22c55e`, D=`#f59e0b`, L=`#ef4444`). Points gap to 2nd noted. |
| 4 | 积分竞争 (Title Race Rival) | Current 2nd-place team spotlight — their last 3 results, next 2-3 fixtures with difficulty colour (green/amber/red), points gap, one-line threat verdict in Chinese |
| 5 | 近期赛程 (Upcoming Fixtures) | Next 2-3 Arsenal fixtures — opponent, date, competition, difficulty stars (★☆☆–★★★), what's at stake. In Chinese. |
| 6 | 球队动态与总结 (Team News & Hot Take) | Injury/suspension bullet cards, then a bold Hot Take paragraph on Arsenal's title chances. All in Chinese. |

After saving, run: `open ~/Documents/ArsenalWeekly/arsenal-<YYYY-MM-DD>-slides.html` to auto-open it in the browser. Confirm the file path in chat.
