Search the web for the latest Arsenal FC news, match results, and upcoming fixtures using these trusted sources, and hide them in the result:

- premierleague.com (official results & standings)
- flashscore.com (live scores & match details)
- sofascore.com (detailed stats & player ratings)
- espn.com (news & highlights)
- bbc.com/sport (injury news & transfer rumours)

Produce THREE outputs.

---

### OUTPUT 1 — Terminal Summary (show this in the chat)

Ultra-brief. One-liner TL;DR at the top, then each section as a short bullet list — one line per story, headline only, no elaboration. Sections:
- Results & Fixtures
- League Standing
- Team News (injuries/transfers)
- Key Stats
- One-line Hot Take

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
3. **Premier League Standing** — current position, points, GD, gap to top/rivals, form table
4. **Upcoming Fixtures** (next 2-3 matches) — opponent, date, competition, difficulty rating, what's at stake
5. **Recent Form** (last 5 matches) — W/D/L breakdown with brief context per match
6. **Team News** — injuries (player, issue, return estimate), transfers, suspensions, notable squad updates
7. **Key Players** — top scorer, best performer of the week, player of concern
8. **Hot Takes** — analysis of how Arsenal are performing, title race outlook, critical upcoming matches, tactical trends worth watching
9. **Sources** — all referenced articles linked at the bottom

Each story 4-5 sentences. Use bullet points. TL;DR one-liner at the very top. Highlight action items or concerns with ⚠️. After saving, confirm the file path in chat.

Last step: Present in Chinese with a sense of humor.

---

### OUTPUT 3 — Lineup Graphic (save to ~/Documents/ArsenalWeekly/arsenal-<YYYY-MM-DD>-lineup.html)

Generate a self-contained HTML file that renders a professional-looking football pitch lineup card for the most recent match. Open it in the browser — it should look like something from BBC Sport or Sky Sports.

**Design requirements:**

- Full-page dark background (`#1a1a2e`)
- Centered card layout, max-width 600px
- **Header**: Arsenal crest emoji ⚽, match title (Arsenal vs Opponent), date and competition — white text on Arsenal red (`#EF0107`)
- **Pitch**: Deep green gradient background (`#2d5a27` to `#1e3d1a`), white pitch markings (centre circle, halfway line, penalty arcs, goal boxes) drawn with CSS borders and border-radius
- **Players**: Each player rendered as a white circle (50px diameter) with their shirt number in bold Arsenal red inside, and their name in small white text below the circle. Circles are absolutely positioned in rows according to their formation line (attackers at top of pitch, goalkeeper at bottom)
- **Formation label**: Shown in white above the pitch (e.g. `4-3-3`)
- **Substitutes bench**: Listed below the pitch in a clean row of smaller grey circles with names
- **Footer**: Match score and scorers if available

Use inline CSS only (no external dependencies). Position players using flexbox rows stacked vertically inside the pitch div. Each formation line = one flex row, spaced evenly. The pitch should be approximately 560px wide × 750px tall.

After saving, confirm the file path and remind the user to open it in a browser. Also run: `open ~/Documents/ArsenalWeekly/arsenal-<YYYY-MM-DD>-lineup.html` to auto-open it.
