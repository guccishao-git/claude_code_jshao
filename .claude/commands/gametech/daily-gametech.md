I am a project manager at Activision supporting Call of Duty titles. Activision is owned by Microsoft, so Xbox gaming strategy is directly relevant to my work. Search the web for today's latest news in game technology, the gaming industry, Call of Duty, and Microsoft Xbox specifically. Use a casual, scannable tone (assume the reader understands live-service games and backend infrastructure).

Step 1: Search these trusted sources, and hide them in the result:

- gamedeveloper.com (Game Developer — engineering & production deep dives)
- venturebeat.com (GamesBeat section — industry news & deals)
- kotaku.com (player-facing news, trends, CoD and Xbox coverage)
- xbox.com/news (official Xbox announcements & Game Pass updates) 

Produce TWO outputs:

---
Step 2:
### OUTPUT 1 — Terminal Summary (show this in the chat)

Ultra-brief. One-liner TL;DR at the top, then each section as a short bullet list — one line per story, headline only, no elaboration. Sections:
- Call of Duty & Activision
- Microsoft Xbox
- Game Tech & Infrastructure
- Industry Moves
- New Releases Worth Playing (2-3 games, include indie gems)
- One-line Hot Take

Flag anything needing attention with ⚠️. No sources needed here.

---
Step 3:
### OUTPUT 2 — Daily Doc (save to ~/Documents/GameNewsDaily/<YYYY-MM-DD>.md)

Full write-up with the following sections:
1. **Call of Duty & Activision** (top 2-3 stories) — game updates, patches, season launches, player reception, Activision/Microsoft news, studio announcements
2. **Microsoft Xbox** (top 2-3 stories) — Xbox hardware, Game Pass, Xbox Game Studios, Microsoft Gaming strategy, first-party titles, Xbox platform policies, Phil Spencer news
3. **Game Tech & Infrastructure** (top 2-3 stories) — game engine updates (Unreal, Unity, IW Engine mentions), backend/cloud gaming (AWS GameLift, GCP, Azure PlayFab), anti-cheat, netcode, live-service ops
4. **Industry Moves** (top 2-3 stories) — acquisitions, layoffs, funding rounds, publisher strategies, platform news (PlayStation, Xbox, PC/Battle.net)
5. **New Releases Worth Playing** — 2-3 recently released games across any platform or genre (include indie gems). For each: what it is, why it's interesting, who it's for, and a one-line verdict on whether it's worth your time.
7. **Hot Takes** — quick analysis: what matters for live-service games like CoD and the broader Microsoft Gaming umbrella, any trends worth flagging to leadership or engineering
8. **Sources** — all referenced articles linked at the bottom

Each story 4-5 sentences. Use bullet points. TL;DR one-liner at the very top. Highlight action items with ⚠️. After saving, confirm the file path in chat.

---
Step 4:
### OUTPUT 3 — Webpage (save to ~/Documents/GameNewsDaily/<YYYY-MM-DD>.html)

Generate a single self-contained HTML file using the **Ops Briefing Terminal** aesthetic:

**Design specs:**
- Fonts: `Barlow Condensed` (headings, condensed labels) + `IBM Plex Mono` (meta, tags, sources) + `Barlow` (body) via Google Fonts
- Colors: dark bg `#05080f`, CoD orange `#ff6b20`, Xbox green `#2ecc71`, Tech cyan `#00c8ff`, Industry red `#ff3c5a`, Hot takes purple `#c084fc`
- Background: hex-grid SVG pattern + grain noise overlay + subtle radial color bleeds
- Grain overlay: fixed `position`, SVG `feTurbulence` noise, `z-index: 9999`, `pointer-events: none`

**Layout structure (top to bottom):**
1. **Sticky topbar** — brand label `◈ GAME INTEL`, live dot + date + topics, scrolling intel ticker (color-coded by section), `PM USE ONLY` badge
2. **Hero** — eyebrow `DAILY INTELLIGENCE BRIEFING // WEEK {N}`, large 3-line `Barlow Condensed 800` headline using the day's 3 biggest stories, TL;DR block with orange left border
3. **4-section grid** (2×2) — CoD / Xbox / Tech / Industry, each with section number, colored title (`font-size: 20px`, `letter-spacing: 0.15em`), colored status dot, story cards
4. **Hot Takes** — full-width purple section, 2×2 card grid with hover-lift effect
5. **Sources** — collapsible toggle, monospace link chips
6. **Footer** — left: date/internal label, right: PM attribution

**Story cards:**
- Regular: title `font-size: 20px`, bullet list `font-size: 15.5px`, hover → `translateX(4px)`
- Warning (`⚠` stories): red border-left `3px solid var(--industry)`, red-tinted background, `⚠` icon prefix in title
- Body base font-size: `17px`
- Section titles: `font-size: 20px`, `letter-spacing: 0.15em`, uppercase

**Ticker:** duplicate items for seamless loop, `animation: ticker 40s linear infinite`, color-coded tags per section, `mask-image` fade on edges

After saving, open the file in the browser and confirm the file path in chat.
