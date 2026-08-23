"""
Arsenal Weekly Slides Generator
Calls the Anthropic API (claude-sonnet-4-6 + web_search) to fetch the latest
Arsenal FC data and generate a self-contained Champions Kit HTML slide deck.

Outputs:
  - docs/arsenal-weekly.html  (committed + pushed to GitHub Pages)
"""

import anthropic
import json
import os
import re
import sys
import time
import urllib.request

REPO_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_FILE = os.path.join(REPO_DIR, "docs", "arsenal-weekly.html")

# ── ESPN standings fetcher (deterministic data source) ─────────────────────────
# ESPN embeds the full PL standings as a JSON array in the page HTML, so we can
# pull structured P / W / D / L / GD / Pts without asking the LLM to read prose.

ESPN_STANDINGS_URL = "https://site.api.espn.com/apis/v2/sports/soccer/eng.1/standings"
_ESPN_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

# Map ESPN displayName → Chinese name for prompt injection
ESPN_TEAM_ZH = {
    "Arsenal": "阿森纳",
    "Manchester City": "曼城",
    "Manchester United": "曼联",
    "Liverpool": "利物浦",
    "Aston Villa": "阿斯顿维拉",
    "Chelsea": "切尔西",
    "Tottenham Hotspur": "热刺",
    "Newcastle United": "纽卡斯尔",
    "Brighton & Hove Albion": "布莱顿",
    "West Ham United": "西汉姆联",
    "Crystal Palace": "水晶宫",
    "Fulham": "富勒姆",
    "Brentford": "布伦特福德",
    "Everton": "埃弗顿",
    "Wolverhampton Wanderers": "狼队",
    "Nottingham Forest": "诺丁汉森林",
    "Bournemouth": "伯恩茅斯",
    "Burnley": "伯恩利",
    "Leeds United": "利兹联",
    "Sunderland": "桑德兰",
}


def fetch_espn_standings(top_n: int = 5) -> list[dict]:
    """
    Pull the top-N PL standings from ESPN's public site API.
    Returns dicts with: rank, team_en, team_zh, p, w, d, l, gd, pts.
    Raises RuntimeError on parse failure (caller decides whether to fall back).
    """
    req = urllib.request.Request(ESPN_STANDINGS_URL, headers={"User-Agent": _ESPN_UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        data = json.loads(r.read().decode("utf-8", errors="replace"))

    entries = data.get("standings", {}).get("entries")
    if not entries:
        children = data.get("children", [])
        if children:
            entries = children[0].get("standings", {}).get("entries")
    if not entries:
        raise RuntimeError("ESPN API format changed — could not find standings entries")

    def to_int(v):
        try:
            return int(round(float(v)))
        except (TypeError, ValueError):
            return None

    out: list[dict] = []
    for i, e in enumerate(entries[:top_n], start=1):
        team_en = e["team"]["displayName"]
        stats = {s["name"]: s for s in e.get("stats", [])}
        p = to_int(stats.get("gamesPlayed", {}).get("value"))
        w = to_int(stats.get("wins", {}).get("value"))
        d = to_int(stats.get("ties", {}).get("value"))
        l = to_int(stats.get("losses", {}).get("value"))
        pts = to_int(stats.get("points", {}).get("value"))
        gd_raw = to_int(stats.get("pointDifferential", {}).get("value"))
        if None in (p, w, d, l, pts, gd_raw):
            raise RuntimeError(f"ESPN API missing fields for {team_en}")
        if w + d + l != p:
            raise RuntimeError(
                f"ESPN data inconsistent for {team_en}: P={p} but W+D+L={w+d+l}"
            )
        gd = f"+{gd_raw}" if gd_raw >= 0 else str(gd_raw)
        out.append({
            "rank": i,
            "team_en": team_en,
            "team_zh": ESPN_TEAM_ZH.get(team_en, team_en),
            "p": p, "w": w, "d": d, "l": l,
            "gd": gd, "pts": pts,
        })
    return out


def build_standings_prompt_block(standings: list[dict]) -> str:
    """Format the standings as a ground-truth block to prepend to the prompt."""
    header = (
        "**⚠️ GROUND TRUTH — PREMIER LEAGUE STANDINGS (verified from ESPN, "
        "use these EXACT numbers in Slide 3 — do NOT modify, recalculate, "
        "or replace with web_search results):**\n\n"
        "| 排名 | 球队 (EN / 中) | 赛 | 胜 | 平 | 负 | 净 | 积分 |\n"
        "|------|----------------|----|----|----|----|----|------|\n"
    )
    lines = [
        f"| {s['rank']} | {s['team_en']} / {s['team_zh']} | "
        f"{s['p']} | {s['w']} | {s['d']} | {s['l']} | {s['gd']} | {s['pts']} |"
        for s in standings
    ]
    note = (
        "\n\n**Important rules tied to this ground-truth table:**\n"
        "- Use the Chinese team names shown above in Slide 3.\n"
        "- The number of matches played (赛) may differ between teams "
        "(games in hand). DO NOT homogenise — use the exact P shown.\n"
        "- Slide 3's points-gap line: gap = (1st 积分) − (2nd 积分). Compute "
        "from the table above, do not invent.\n"
        "- Slide 4's chart `rivalPts` array: the final element must equal "
        "the rival's Pts above ONLY IF the rival has played the same number "
        "of GWs as Arsenal. If rival's P is less than Arsenal's P, the final "
        "element of `rivalPts` must be `null` (game not yet played) and the "
        "previous element must equal the rival's current Pts.\n\n"
    )
    return header + "\n".join(lines) + note

# ── Prompt ─────────────────────────────────────────────────────────────────────

PROMPT = """
Search the web for the latest Arsenal FC news, match results, and upcoming fixtures
using these trusted sources:

- premierleague.com/tables (official standings)
- bbc.com/sport/football/premier-league/table (cross-check standings)
- flashscore.com (live scores & match details)
- sofascore.com (detailed stats & player ratings)
- espn.com (news & highlights)
- bbc.com/sport (injury news & transfer rumours)
- arsenal.com/fixtures (upcoming fixtures)

**Before producing the final HTML, verify ALL statistics using the checklist below.
Never infer, estimate, or hallucinate — only use confirmed figures.
If a stat can only be found from one source, mark it "(unverified)".**

**① Match Results & Goalscorers**
- Confirm final score from at least 2 sources (flashscore.com + espn.com or bbc.com/sport)
- Confirm each goalscorer name, minute, and type (open play / penalty / OG) from at least 2 sources
- Confirm red cards, assist credits, and key events from match reports — do not guess

**② Premier League Standings**
- Fetch the full table from premierleague.com/tables
- Cross-check games played (P), W, D, L for Arsenal AND the current 2nd-place team against a second source
- Sanity check: Played must equal W + D + L for every team shown — if numbers don't add up, re-fetch and correct
- Never infer or estimate match counts — only use confirmed figures from at least two sources

**③ Form Table (Last 5)**
- Verify each of Arsenal's last 5 results (opponent, score, W/D/L) from flashscore.com or sofascore.com
- Do not reconstruct form from season aggregate stats — use the actual match list

**④ Injury & Suspension List**
- Use at least one official or specialist source (arsenal.com, physioroom.com, bbc.com/sport, or 3addedminutes.com)
- Note expected return timeline only if a source explicitly states it — otherwise write "TBD"
- Flag suspended players separately from injured players

**⑤ Title Race Rival Stats**
- Verify rival's W, D, L, GD, and points with the same P = W + D + L sanity check
- Confirm rival's last 3 results from flashscore.com or sofascore.com — include scores, not just W/D/L
- Confirm rival's upcoming fixtures from their official club site or premierleague.com

**⑥ Upcoming Arsenal Fixtures**
- Verify dates, opponents, and competition from arsenal.com/fixtures or premierleague.com
- Do not infer fixture dates from memory — fetch them

**⑦ Points Race Data (for chart)**
- Fetch Arsenal's cumulative points by gameweek for the current Premier League season from premierleague.com or fbref.com
- Fetch the same for the current 2nd-place team
- Provide at minimum the last 10 gameweeks; full season preferred
- CRITICAL data rules:
  - Each array index N represents the total cumulative points AFTER gameweek N has been played
  - If a team had a blank gameweek (no fixture scheduled), repeat the previous value — do NOT skip the index
  - If a gameweek has not yet been played, use null — do NOT carry forward the last value
  - Both arrays must have the same length as the labels array
  - Verify: the final non-null value in arsenalPts must equal Arsenal's current points total from the standings (step ②)
  - Verify: the final non-null value in rivalPts must equal the rival's current points total from the standings (step ②)
- Format as two JS arrays: labels (GW1, GW2…), arsenalPts[], rivalPts[]

---

Now generate a self-contained, full-screen scroll-snap HTML slide deck (7 slides) summarising
the week in Arsenal. Use the **Champions Kit theme** with the exact design spec below.
**所有文字内容必须用中文，语气风趣幽默——像懂球的球迷在聊天，不是新闻通稿。适当使用足球黑话、轻度吐槽和搞笑评论。Output only the HTML — no markdown, no code fences.**
**阿森纳的昵称是"枪手"，绝对不要写"红军"（那是利物浦的外号）。**

**Design theme — Champions Kit (preserve exactly):**
Inspired by Arsenal's navy/bronze/gold "CHAMPIONS 26" commemorative jersey — deep navy canvas,
metallic bronze/gold display accents, crimson + gold double-stripe chrome echoing the collar/cuff trim.

CSS variables:
  --bg: #0B1730
  --navy-hi: #16264A
  --crimson: #C8102E
  --crimson-dim: rgba(200,16,46,0.25)
  --crimson-glow: rgba(200,16,46,0.5)
  --bronze: #A9863F
  --bronze-hi: #D4B876
  --gold: #E8B84B
  --gold-dim: rgba(232,184,75,0.2)
  --text: #F2EEE6
  --text-muted: rgba(242,238,230,0.6)

Fonts (load via Google Fonts):
  Syne 600–800 (display/headings)
  Noto Sans SC 300–700 (Chinese body text — use for all Chinese paragraphs and descriptions)
  Oswald 400–700 (standalone stats/scores only — e.g. "3-1" score displays, labels, tags, section labels)
  IMPORTANT: Never apply Oswald to running Chinese body text — use Noto Sans SC for all Chinese paragraphs and descriptions.

Chart.js (CDN): https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js

Layout:
  scroll-snap-type: y mandatory on html ONLY
  Each .slide = 100vw × 100dvh, scroll-snap-align: start
  CRITICAL — scroll container must be html ONLY:
    html { overflow-y: scroll; scroll-snap-type: y mandatory; background: var(--bg); }
    body { font-family: 'Noto Sans SC', sans-serif; color: var(--text); background: var(--bg); }
  NEVER set overflow: hidden or height: 100% on body — doing so clips all slides beyond the first viewport, making only slide 1 visible.
  Never apply overflow-y: scroll or scroll-snap-type to body — doing so creates two scroll containers and breaks scrollIntoView() navigation.

Background FX on every slide (make them dramatic and vivid):
  .kit-stripe — a fixed 8px-tall chrome bar at the very top of every slide, split into three flex
    segments echoing the jersey's collar/cuff trim: crimson (flex:1), gold (flex:0.4), crimson (flex:1).
    position: fixed; top:0; left:0; right:0; z-index:50; display:flex.
  .chevrons — a very subtle jersey-texture overlay across the whole slide: two overlapping
    repeating-linear-gradient triangles/chevrons at 135deg and 45deg, ~40px repeat, rgba(255,255,255,0.02-0.025)
    stripes on transparent, opacity 0.5. Purely textural — must never reduce text contrast.
  .beams — 4 light beams from top, width clamp(80px,12vw,180px), opacity 0.75, mix-blend-mode: screen,
    background gradient from var(--gold) at ~40% alpha → rgba(200,16,46,0.18) → transparent,
    sway ±8deg with scaleX(1.15) at peak; beam 2 opacity 0.5, beam 3 opacity 0.6
  .pitch-bg — subtle grid at bottom 30% (white hairlines, unchanged)
  .center-glow — wide radial gradient (width 110%, top -15%), pulsing opacity animation (glowPulse 4s):
    background: radial-gradient(ellipse at 50% 20%, rgba(232,184,75,0.35) 0%, rgba(200,16,46,0.14) 40%, transparent 70%)

Crest watermark on every slide:
  <img src="https://resources.premierleague.com/premierleague/badges/t3@x2.png"
       onerror="this.style.display='none'" class="crest-watermark">
  opacity: 0.07, positioned right side, pointer-events: none

Typography (all clamp):
  title: clamp(2.2rem, 6vw, 5rem), text-shadow: 0 0 60px rgba(232,184,75,0.35), 0 2px 4px rgba(0,0,0,0.6)
  h2: clamp(1.5rem, 3.5vw, 2.75rem), text-shadow: 0 0 40px rgba(232,184,75,0.25), 0 2px 4px rgba(0,0,0,0.5)
  body: clamp(0.78rem, 1.3vw, 1rem)

Bronze gradient text-clip (signature move — echoes the jersey's metallic "26" numeral):
  Apply to the cover's highlighted <em> word/stat and to one accent word per slide's h2, e.g.:
    background: linear-gradient(180deg, var(--bronze-hi) 0%, var(--bronze) 55%, #7a5f2b 100%);
    -webkit-background-clip: text; background-clip: text; color: transparent;
  This changes COLOR only — never override font-family on these elements (see cover h1 rule below).

Score display (.score-display): Oswald, color var(--gold), text-shadow: 0 0 30px rgba(232,184,75,0.5), 0 0 60px rgba(232,184,75,0.15)
Score team names (.score-team): Syne bold, font-size clamp(1.1rem,2.5vw,1.8rem), color var(--text), text-shadow: 0 0 20px rgba(232,184,75,0.25)

.tag component: uppercase, letter-spacing 0.25em, color var(--gold), ::before = 18px gold horizontal line

Cards:
  background: rgba(169,134,63,0.07)
  border: 1px solid var(--crimson-dim)
  border-radius: 8px
  box-shadow: 0 4px 24px rgba(200,16,46,0.08), inset 0 1px 0 rgba(255,255,255,0.05)

Nav dots: fixed right side, active = var(--gold) with pulsing gold box-shadow animation (dotPulse 2s), inactive = var(--text-muted).
MANDATORY: Place a <nav class="nav-dots" id="navDots"> element immediately after <body> with one <button class="nav-dot" data-idx="N"> per slide (N = 0-based index). First button gets class="nav-dot active". Example for 7 slides:
  <nav class="nav-dots" id="navDots">
    <button class="nav-dot active" data-idx="0" title="封面"></button>
    <button class="nav-dot" data-idx="1" title="本周战报"></button>
    <button class="nav-dot" data-idx="2" title="积分榜"></button>
    <button class="nav-dot" data-idx="3" title="积分追逐战"></button>
    <button class="nav-dot" data-idx="4" title="积分竞争"></button>
    <button class="nav-dot" data-idx="5" title="近期赛程"></button>
    <button class="nav-dot" data-idx="6" title="球队动态"></button>
  </nav>

Nav JS: place a plain <script> block immediately before </body> (not in DOMContentLoaded). It must:
  1. Select all section.slide elements and all #navDots .nav-dot buttons
  2. Wire click on each dot → slides[data-idx].scrollIntoView({behavior:'smooth'})
  3. Use IntersectionObserver(threshold:0.5) to add/remove 'active' class on dots as slides enter view
  4. Listen for ArrowDown/ArrowRight (next) and ArrowUp/ArrowLeft (prev) keydown events
Example JS block:
  <script>
  (function () {
    var slides = Array.from(document.querySelectorAll('section.slide'));
    var dots   = Array.from(document.querySelectorAll('#navDots .nav-dot'));
    function goTo(i) { if (slides[i]) slides[i].scrollIntoView({ behavior: 'smooth' }); }
    dots.forEach(function (d) { d.addEventListener('click', function () { goTo(parseInt(this.dataset.idx, 10)); }); });
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (e) { if (e.isIntersecting) { var i = slides.indexOf(e.target); dots.forEach(function (d, j) { d.classList.toggle('active', i === j); }); } });
    }, { threshold: 0.5 });
    slides.forEach(function (s) { obs.observe(s); });
    document.addEventListener('keydown', function (e) {
      var cur = slides.findIndex(function (s) { return s.getBoundingClientRect().top > -10; });
      if (e.key === 'ArrowDown' || e.key === 'ArrowRight') goTo(Math.min(cur + 1, slides.length - 1));
      if (e.key === 'ArrowUp'   || e.key === 'ArrowLeft')  goTo(Math.max(cur - 1, 0));
    });
  })();
  </script>

Animations: fadeUp reveal on slide content entry; beamSway on light beams; glowPulse on center-glow; dotPulse on active nav dot; crestFloat 5s ease-in-out infinite (translateY 0 → -10px → 0) on the cover crest

**Slide structure (7 slides, all content in Chinese with witty football fan humor):**

Slide 1 — 封面 (Cover):
  Use a two-column layout (.cover-layout, flexbox, space-between):

  LEFT COLUMN (.cover-left):
  - "阿森纳本周快报" masthead (Oswald, uppercase, letter-spacing 0.35em, color var(--gold),
    with a 32px gold line before and a fading gold line after filling remaining width)
  - A punchy 3-line <h1> headline (font-size clamp(2.8rem,5.5vw,5rem), line-height 0.95)
    distilling the week into 3 short Chinese lines — wrap the key stat/result in <em> styled with the
    bronze gradient text-clip technique described above (color only, keep inherited font-family).
    Always use numerals not Chinese characters for numbers (e.g. "3连胜" not "三连胜"). Make it funny like a meme caption.
    Example: "3胜.<br><em>领先7分</em><br>稳了？"
    CRITICAL FONT RULE: The h1 CSS must be font-family:'Noto Sans SC',sans-serif; font-weight:900 — NOT Syne.
    Reason: Syne's Latin numerals have completely different optical weight from Chinese characters and look jarring.
    Noto Sans SC covers both numerals and Chinese consistently at weight 900.
    NEVER wrap numbers or <em> or <span> inside the h1 with any other font-family override.
  - A short crimson→gold gradient divider bar (width clamp(40px,8vw,80px), height 3px)
  - Current date in Chinese format (Oswald, uppercase, letter-spacing 0.2em, muted color)

  RIGHT COLUMN (.cover-right):
  - Arsenal crest <img> (use high-res: https://resources.premierleague.com/premierleague/badges/t3@x2.png), width clamp(160px,26vw,320px),
    filter: drop-shadow gold glow, animation: crestFloat 5s ease-in-out infinite

  DO NOT add any body text or paragraph description on the cover — keep it minimal and sharp.

Slide 2 — 本周战报 (Match Report):
  Last 1–2 results — score, competition, key goalscorers, brief tactical note.
  Use large score display with Oswald font.
  Add a funny one-liner reaction to each result in Chinese (e.g. "赢了！枪手再次证明自己是真的！" or "又平了？球迷心脏受不了。").
  All labels, section headers, match info in Chinese.

Slide 3 — 积分榜 (League Standing):
  PL table showing top 5 teams — Arsenal row highlighted with a bronze/gold background tint (rgba(169,134,63,0.14)).
  Columns in Chinese: 排名, 球队, 赛, 胜, 平, 负, 净, 积分
  W/D/L form pills for last 5 (W=#22c55e, D=#f59e0b, L=#ef4444) — label as 胜/平/负
  Points gap to 2nd noted below table with a cheeky Chinese comment.

Slide 4 — 积分追逐战 (Points Race):
  Chart.js line chart using data from step ⑦, two datasets:
  - Arsenal: borderColor #C8102E (crimson), backgroundColor rgba(200,16,46,0.12), fill true
  - 追赶者 (current 2nd-place team name in Chinese if known, else English): borderColor #E8B84B (gold), backgroundColor transparent, fill false, borderDash [6,3]
  Both lines: borderWidth 2.5, pointRadius 3, pointHoverRadius 6, pointBackgroundColor matching borderColor, tension 0.3
  X-axis: gameweek labels (GW1, GW2…). Y-axis: cumulative points, position "right".
  Chart layout must NOT overflow the slide — see Chart.js layout spec below.
  Points gap shown as a styled <p> tag below the legend in Chinese, not inside canvas.

Slide 5 — 积分竞争 (Title Race):
  Current 2nd-place team spotlight — their last 3 results with scores,
  next 2–3 fixtures with difficulty colour (green=easy/amber=medium/red=hard),
  points gap, one-line threat verdict in Chinese. Roast them a little if they're struggling.
  All section labels, fixture info, and commentary in Chinese.
  Font rules (Champions Kit theme — enforce exactly):
  - Section labels like "近3场战绩" and "接下来的赛程": font-family:'Oswald',sans-serif (NOT Syne)
  - Difficulty spans (● 轻松 / ● 困难 / ● 中等): add font-family:'Oswald',sans-serif inline
  - Short disclaimer notes: font-family:'Oswald',sans-serif
  - Standalone stats/scores (e.g. "−7 分"): inherits Oswald from parent <p>; do NOT add redundant inner font-family
  - Running verdict text: Noto Sans SC (default body) is fine

Slide 6 — 近期赛程 (Upcoming Fixtures):
  Next 2–3 Arsenal fixtures — opponent, date, competition,
  difficulty stars (★☆☆–★★★), what's at stake.
  All in Chinese with dramatic flair — hype up the big matches, mock the easy ones.
  FIXTURE CARD LAYOUT (critical — prevents text wrapping one character per line):
  Each .fixture-item must use: display:flex; flex-wrap:wrap; align-items:center; gap: clamp(6px,1vw,12px);
  The competition label (.fixture-comp): flex-shrink:0; min-width:60px;
  The middle info column (flex:1): also add min-width:0 to prevent flex shrink collapse.
  The stakes/description row: flex-basis:100% so it wraps to its own line below.

Slide 7 — 球队动态与热评 (Team News & Hot Take):
  Top half: injury/suspension cards (.injury-grid) with sympathetic or sarcastic Chinese commentary.

  Bottom half: Hot Take section (.hot-take-section) — THIS SECTION IS MANDATORY, never omit it.
  It must contain THREE components in this exact order:

  1. .hot-take-main — a bold italic quote in Syne 700, font-size clamp(1rem,2vw,1.35rem),
     left crimson border (4px solid var(--crimson)), gradient background. One punchy opinionated
     sentence in Chinese about Arsenal's week or title chances — make it sharp, funny, and confident.

  2. .hot-take-pills — two or three side-by-side cards (.hot-take-pill), each with:
     - A .hot-take-pill-label (Oswald, gold, uppercase) naming the topic in Chinese (e.g. "冠军争夺", "关键对决", "隐忧")
     - A short 1-2 sentence take in Noto Sans SC, muted text, in Chinese

  Be opinionated and specific — reference actual players, opponents, and stats from the week. Be funny and theatrical.

  CLOSING STRUCTURE FOR SLIDE 7 (must follow this exactly):
    </div>  ← closes .hot-take-section
  </div>  ← closes .slide-content (or equivalent wrapper div)
</section>  ← closes the slide
  Then immediately the nav JS <script> block, then </body></html>.
  DO NOT add any extra <section>, <footer>, or <div class="container"> after the hot-take-section.

**Chart.js layout & styling rules (apply to the chart slide):**

Viewport fitting — CRITICAL (no slide may scroll):
- Give both chart slide <section> elements class="chart-slide"
- Inside the slide, use a flex-column layout: tag + h2 are flex:0 auto; the card is flex:1 1 0 with min-height:0 so it fills remaining space
- The canvas wrapper: position:relative; height:clamp(160px,42vh,360px); min-height:clamp(160px,42vh,360px); flex:0 0 auto
  CRITICAL: do NOT use flex:1 1 0 + min-height:0 on the canvas wrapper — that lets flexbox shrink it to 0, making the chart invisible
- Add @media (max-height:700px) reducing canvas-wrap height to clamp(120px,38vh,260px)
- canvas element: width:100%!important; height:100%!important; display:block
- Card container: background rgba(255,255,255,0.04); border 1px solid rgba(200,16,46,0.18); border-radius 8px; overflow:hidden

Chart.js config (both charts):
- responsive:true, maintainAspectRatio:false (required for height-constrained wrapper)
- animation: duration 800, easing "easeOutQuart"
- plugins.legend.display:false — use a custom HTML legend instead
- Tooltip: bg rgba(11,23,48,0.95), border rgba(200,16,46,0.4) 1px, title/body color #F2EEE6, cornerRadius 6, titleFont Oswald 13px, bodyFont 'Noto Sans SC' 12px
- Both axes: grid.color rgba(255,255,255,0.05), grid.drawBorder false, border.display false, ticks.color rgba(242,238,230,0.5), ticks.font Oswald 11px, ticks.maxTicksLimit 10

Custom HTML legend: a flex row below the canvas-wrap with 10px coloured dots (border-radius 50%) and 'Noto Sans SC' 0.75rem labels in rgba(242,238,230,0.7). For reference-line entries use a 16×2px rectangle dot instead of a circle.

Slide 4 annotation: one line below legend — Oswald 0.8rem rgba(242,238,230,0.5) — showing "▲ AHEAD BY X PTS" (gold) or "▼ BEHIND BY X PTS" (crimson).

**Important:**
- The output must be a single complete HTML document starting with <!DOCTYPE html> and ending with </html>
- No markdown, no code fences, no commentary — raw HTML only
- NEVER output any reasoning, search notes, or status messages inside the HTML — if you need to search mid-generation, do it silently. Any stray text inside the HTML will corrupt the page.
- All slide content in Chinese with witty football fan humor — casual, funny, and opinionated
- Slide 7 MUST include the full hot-take section (.hot-take-main + .hot-take-pills) — do not truncate or omit it
- After slide 7's </section>, output ONLY the nav JS block then </body></html> — no extra sections, footers, or wrappers
- Embed everything inline (no external CSS files, no external JS files except Google Fonts CDN and Chart.js CDN)
- Load Chart.js from: https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js
- IMPORTANT: Initialise each chart with an inline <script> tag placed IMMEDIATELY after that slide's closing </section> tag — NOT in a DOMContentLoaded block at the end of the document. This ensures the chart JS is output early and survives any token truncation.
- DO NOT add any additional <script> blocks after the last </section>. The final document structure must be: last </section>, then a single nav/keyboard JS block, then </body></html>. Never output a second Chart.js CDN tag or a second chart initialisation block.
- Add class="chart-slide" to the <section> element for Slide 4 so the chart layout CSS applies
- NEVER use a fixed pixel height on .slide — every slide must remain height:100vh; height:100dvh; overflow:hidden
- The chart canvas MUST have its wrapper div constrained to clamp(160px,42vh,360px) so it never causes overflow
"""

# ── Agentic loop ───────────────────────────────────────────────────────────────

def generate_slides(prompt: str = PROMPT) -> str:
    """Call Claude with web_search in an agentic loop; return full HTML string."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = [{"role": "user", "content": prompt}]

    print("Starting Arsenal weekly slides generation…")

    all_text_parts: list[str] = []  # accumulates HTML across continuation calls
    iteration = 0
    while True:
        iteration += 1
        print(f"  API call #{iteration} (stop_reason pending)…")

        # Retry up to 5 times on rate limit errors with exponential backoff
        for attempt in range(5):
            try:
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=16000,
                    tools=[{"type": "web_search_20250305", "name": "web_search"}],
                    messages=messages,
                )
                break
            except anthropic.RateLimitError as e:
                wait = 60 * (2 ** attempt)  # 60s, 120s, 240s, 480s, 960s
                print(f"  Rate limit hit (attempt {attempt+1}/5) — waiting {wait}s…")
                time.sleep(wait)
                if attempt == 4:
                    print("  Rate limit retry exhausted.", file=sys.stderr)
                    raise

        print(f"  stop_reason={response.stop_reason}")

        # Collect text blocks from this response
        has_tool_use = any(block.type == "tool_use" for block in response.content)
        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        all_text_parts.extend(text_parts)

        if response.stop_reason == "end_turn":
            return "\n".join(all_text_parts)

        if response.stop_reason == "max_tokens":
            if has_tool_use:
                # Still in the data-gathering phase — continue normally
                print("  max_tokens hit during tool_use, continuing loop…")
            elif "".join(all_text_parts).strip():
                # HTML generation was truncated — use a fresh minimal context
                # so the continuation call stays well under the input token limit
                print("  max_tokens hit during HTML generation, requesting continuation…")
                accumulated = "\n".join(all_text_parts)
                tail = accumulated[-800:]  # last ~800 chars as cut-off context
                messages = [
                    {
                        "role": "user",
                        "content": (
                            "You are completing an HTML document that was cut off. "
                            "Here are the last characters generated so far:\n\n"
                            f"...{tail}\n\n"
                            "Continue the HTML from exactly where it was cut off. "
                            "Do not repeat any HTML. Output only the continuation until </html>."
                        ),
                    }
                ]
                continue
            else:
                print("  max_tokens hit with no usable content.", file=sys.stderr)
                sys.exit(1)

        if response.stop_reason not in ("tool_use", "max_tokens"):
            print(f"  Unexpected stop_reason: {response.stop_reason}", file=sys.stderr)
            sys.exit(1)

        # Append assistant turn
        messages.append({"role": "assistant", "content": response.content})

        # Build tool results (web_search handles its own fetching; we pass empty content)
        tool_results = [
            {
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": "",
            }
            for block in response.content
            if block.type == "tool_use"
        ]

        if not tool_results:
            print("  No tool_use blocks found despite tool_use stop_reason.", file=sys.stderr)
            sys.exit(1)

        messages.append({"role": "user", "content": tool_results})

        if iteration > 30:
            print("  Exceeded 30 iterations — aborting.", file=sys.stderr)
            sys.exit(1)


# ── HTML extraction ────────────────────────────────────────────────────────────

def sanitise_html(html: str) -> str:
    """Remove any leaked model reasoning text from inside the HTML."""
    # Pattern: text node content that looks like model commentary (English sentences
    # appearing between HTML tags mid-document, not inside a <script>/<style> block)
    # Strategy: remove lines that are pure prose English outside tag context
    lines = html.splitlines()
    cleaned = []
    in_script_or_style = False
    for line in lines:
        stripped = line.strip()
        # Track script/style blocks (skip sanitisation inside them)
        if re.match(r'<(script|style)[\s>]', stripped, re.IGNORECASE):
            in_script_or_style = True
        if re.match(r'</(script|style)>', stripped, re.IGNORECASE):
            in_script_or_style = False
            cleaned.append(line)
            continue
        if in_script_or_style:
            cleaned.append(line)
            continue
        # Drop lines that are plain English prose with no HTML tags
        # (likely leaked model reasoning).
        # Skip if the line is clearly an HTML attribute continuation
        # (contains attr="value" syntax or ends a tag with '>') — these are
        # legitimate parts of multi-line <img>/<a>/etc. tags.
        if (stripped
                and not stripped.startswith('<')
                and not stripped.startswith('//')
                and re.search(r'[A-Za-z]{6,}', stripped)
                and not re.search(r'[^\x00-\x7F]', stripped)  # no CJK = suspicious
                and not re.search(r'=\s*["\']', stripped)     # has HTML attr syntax
                and not stripped.endswith('>')                # closes a tag
                and len(stripped) > 20):
            print(f"  [sanitise] Removed leaked text: {stripped[:80]!r}", file=sys.stderr)
            continue
        cleaned.append(line)
    return "\n".join(cleaned)


def extract_html(raw: str) -> str:
    """Extract <!DOCTYPE html>…</html> block from the response."""
    # Strip markdown code fences if Claude wrapped it anyway
    raw = re.sub(r"```html\s*", "", raw)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)

    # Greedy match: from first <!DOCTYPE to last </html>
    match = re.search(r"(<!DOCTYPE html>.*</html>)", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Continuation calls may not repeat <!DOCTYPE — stitch from first <html
    if "<html" in raw.lower():
        return raw.strip()

    # If still truncated (continuation didn't close </html>), return as-is
    if "<!DOCTYPE" in raw or "<html" in raw.lower():
        return raw.strip()

    print("ERROR: Could not find HTML block in response.", file=sys.stderr)
    print("Raw response snippet:", raw[:500], file=sys.stderr)
    sys.exit(1)


EXPECTED_SLIDE_COUNT = 7


def dedupe_html(html: str) -> str:
    """
    Guard against duplicated documents produced by the max_tokens continuation
    flow: if the model's continuation re-emits a second copy of the deck
    (its own closing slides + nav script + </body></html>) instead of cleanly
    resuming, the extractor's greedy first-DOCTYPE-to-last-</html> match will
    swallow both copies concatenated together — doubling every slide from the
    cutoff point onward (visible as duplicate nav dots, two simultaneously
    "active" dots, etc.).

    Fix: walk each </html> occurrence in order and cut the document at the
    FIRST one that already contains at least EXPECTED_SLIDE_COUNT slide
    sections. Anything after that point is a duplicate/leaked continuation
    artifact and is discarded.
    """
    closes = [m.end() for m in re.finditer(r"</html\s*>", html, re.IGNORECASE)]
    if len(closes) <= 1:
        return html

    for end_idx in closes:
        head = html[:end_idx]
        n_slides = len(re.findall(
            r'<section[^>]+class="[^"]*slide[^"]*"[^>]*>.*?</section>', head, re.DOTALL
        ))
        if n_slides >= EXPECTED_SLIDE_COUNT:
            if end_idx != closes[-1]:
                print(
                    f"  [dedupe] Found {len(closes)} </html> closings; "
                    f"truncated after the first complete document "
                    f"({n_slides} slides) — dropped {len(html) - end_idx} "
                    f"trailing bytes of duplicate/leaked content.",
                    file=sys.stderr,
                )
            return head
    # No occurrence reached the expected slide count — leave as-is; the
    # existing slide-7 / hot-take fallbacks downstream will patch gaps.
    return html


# ── Post-generation validation & auto-fix ──────────────────────────────────────

NAV_JS = """\
<script>
(function () {
  var slides = Array.from(document.querySelectorAll('section.slide'));
  var dots   = Array.from(document.querySelectorAll('#navDots .nav-dot'));
  function goTo(i) { if (slides[i]) slides[i].scrollIntoView({ behavior: 'smooth' }); }
  dots.forEach(function (d) { d.addEventListener('click', function () { goTo(parseInt(this.dataset.idx, 10)); }); });
  var obs = new IntersectionObserver(function (entries) {
    entries.forEach(function (e) { if (e.isIntersecting) { var i = slides.indexOf(e.target); dots.forEach(function (d, j) { d.classList.toggle('active', i === j); }); } });
  }, { threshold: 0.5 });
  slides.forEach(function (s) { obs.observe(s); });
  document.addEventListener('keydown', function (e) {
    var cur = slides.findIndex(function (s) { return s.getBoundingClientRect().top > -10; });
    if (e.key === 'ArrowDown' || e.key === 'ArrowRight') goTo(Math.min(cur + 1, slides.length - 1));
    if (e.key === 'ArrowUp'   || e.key === 'ArrowLeft')  goTo(Math.max(cur - 1, 0));
  });
})();
</script>"""

SLIDE7_FALLBACK = """\
<section class="slide" id="slide-6">
  <div class="beams">
    <div class="beam"></div><div class="beam"></div>
    <div class="beam"></div><div class="beam"></div>
  </div>
  <div class="pitch-bg"></div>
  <div class="center-glow"></div>
  <img src="https://resources.premierleague.com/premierleague/badges/t3@x2.png" onerror="this.style.display='none'" class="crest-watermark" alt="">
  <div class="slide-content" style="overflow-y:auto;max-height:calc(100dvh - 40px);">
    <div class="tag">球队动态 · 热评</div>
    <h2 style="font-family:'Syne',sans-serif;">本周<em>总结</em></h2>
    <div class="hot-take-section" style="margin-top:14px;">
      <div class="hot-take-main" style="border-left:4px solid var(--crimson);padding:12px 16px;background:rgba(169,134,63,0.08);border-radius:4px;margin-bottom:12px;">
        <p style="font-family:'Syne',sans-serif;font-weight:700;font-style:italic;font-size:clamp(1rem,2vw,1.35rem);color:var(--text);margin:0;">没有最顽强，只有更顽强——这就是阿尔特塔的枪手。积分领先，赛程在握，冠军来了。</p>
      </div>
      <div class="hot-take-pills" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <div class="hot-take-pill" style="background:rgba(169,134,63,0.08);border:1px solid rgba(200,16,46,0.25);border-radius:8px;padding:12px;">
          <div class="hot-take-pill-label" style="font-family:'Oswald',sans-serif;color:#E8B84B;text-transform:uppercase;font-size:0.7rem;letter-spacing:0.15em;margin-bottom:5px;">冠军争夺</div>
          <p style="font-family:'Noto Sans SC',sans-serif;font-size:0.78rem;color:rgba(240,237,232,0.6);margin:0;line-height:1.5;">积分领先，赛程在手——枪手只要稳住，奖杯就是囊中之物。</p>
        </div>
        <div class="hot-take-pill" style="background:rgba(169,134,63,0.08);border:1px solid rgba(200,16,46,0.25);border-radius:8px;padding:12px;">
          <div class="hot-take-pill-label" style="font-family:'Oswald',sans-serif;color:#E8B84B;text-transform:uppercase;font-size:0.7rem;letter-spacing:0.15em;margin-bottom:5px;">关键隐忧</div>
          <p style="font-family:'Noto Sans SC',sans-serif;font-size:0.78rem;color:rgba(240,237,232,0.6);margin:0;line-height:1.5;">伤病室人满为患，阿尔特塔的轮换考验正式开始。</p>
        </div>
      </div>
    </div>
  </div>
</section>"""

HOT_TAKE_FALLBACK = """\
    <div class="hot-take-section" style="margin-top:14px;">
      <div class="hot-take-main" style="border-left:4px solid var(--crimson);padding:12px 16px;background:rgba(169,134,63,0.08);border-radius:4px;margin-bottom:12px;">
        <p style="font-family:'Syne',sans-serif;font-weight:700;font-style:italic;font-size:clamp(1rem,2vw,1.35rem);color:var(--text);margin:0;">没有最顽强，只有更顽强——这就是阿尔特塔的枪手。</p>
      </div>
      <div class="hot-take-pills" style="display:grid;grid-template-columns:1fr 1fr;gap:10px;">
        <div class="card hot-take-pill" style="padding:12px;">
          <span class="hot-take-pill-label" style="font-family:'Oswald',sans-serif;color:var(--gold);text-transform:uppercase;font-size:0.7rem;letter-spacing:0.15em;display:block;margin-bottom:6px;">冠军争夺</span>
          <p style="font-family:'Noto Sans SC',sans-serif;font-size:0.78rem;color:var(--text-muted);margin:0;line-height:1.5;">积分领先，赛程在手——枪手只要稳住，奖杯就是囊中之物。</p>
        </div>
        <div class="card hot-take-pill" style="padding:12px;">
          <span class="hot-take-pill-label" style="font-family:'Oswald',sans-serif;color:var(--gold);text-transform:uppercase;font-size:0.7rem;letter-spacing:0.15em;display:block;margin-bottom:6px;">关键隐忧</span>
          <p style="font-family:'Noto Sans SC',sans-serif;font-size:0.78rem;color:var(--text-muted);margin:0;line-height:1.5;">伤病室人满为患，阿尔特塔的轮换考验正式开始。</p>
        </div>
      </div>
    </div>"""


def validate_and_fix(html: str, espn_standings: list[dict] | None = None) -> str:
    """
    Post-generation checks and auto-fixes for recurring issues.
    Runs after sanitise_html(). Prints a report of every fix applied.
    If espn_standings is provided, also performs a numeric cross-check
    against the rendered .pl-table.
    """
    fixes: list[str] = []
    warnings: list[str] = []

    # ── 1. Font: ensure Noto Sans SC is loaded ──────────────────────────────
    if "Noto+Sans+SC" not in html and "Noto Sans SC" not in html:
        html = html.replace(
            "family=Syne:",
            "family=Noto+Sans+SC:wght@300;400;500;700&family=Syne:",
        )
        fixes.append("Added missing Noto Sans SC to Google Fonts link")

    # ── 2. Font: ensure body uses Noto Sans SC, not Inter ───────────────────
    if "font-family: 'Inter', sans-serif" in html or 'font-family:"Inter"' in html:
        html = html.replace("font-family: 'Inter', sans-serif", "font-family: 'Noto Sans SC', sans-serif")
        html = html.replace('font-family:"Inter"', 'font-family:"Noto Sans SC"')
        fixes.append("Replaced Inter body font with Noto Sans SC")

    # ── 3. Fixture card layout: flex-wrap on .fixture-item ──────────────────
    # If .fixture-item CSS exists but lacks flex-wrap:wrap, inject it
    fi_match = re.search(r'(\.fixture-item\s*\{[^}]*?\})', html, re.DOTALL)
    if fi_match:
        fi_css = fi_match.group(1)
        if "flex-wrap" not in fi_css:
            fixed_css = fi_css.replace("display: flex", "display: flex;\n  flex-wrap: wrap")
            html = html.replace(fi_css, fixed_css)
            fixes.append("Added flex-wrap:wrap to .fixture-item")
        if "flex-shrink: 0" not in html and ".fixture-comp" in html:
            # Inject flex-shrink into .fixture-comp
            html = re.sub(
                r'(\.fixture-comp\s*\{)',
                r'\1\n  flex-shrink: 0;',
                html
            )
            fixes.append("Added flex-shrink:0 to .fixture-comp")

    # ── 4. Slide structure: remove junk appended after last </section> ───────
    # Anything between the last </section> and </body> that is NOT a <script> block.
    # MUST run before the slide-count check below: leaked/duplicate continuation
    # content after the true last slide can otherwise get counted as if it were
    # real slide markup, masking a genuinely missing Slide 7.
    last_sec = html.rfind("</section>")
    body_end = html.rfind("</body>")
    if last_sec != -1 and body_end != -1 and last_sec < body_end:
        between = html[last_sec + len("</section>"):body_end]
        # Keep only <script>…</script> blocks in that gap
        scripts = re.findall(r'<script[\s\S]*?</script>', between, re.IGNORECASE)
        clean_between = "\n\n" + "\n".join(scripts) + "\n" if scripts else "\n\n"
        if clean_between.strip() != between.strip():
            html = html[:last_sec + len("</section>")] + clean_between + "</body>" + html[body_end + len("</body>"):]
            fixes.append("Removed junk content appended after last </section>")

    # ── 5. Slide 7: ensure it exists and has a hot-take section ─────────────
    # IMPORTANT: count only *complete* section blocks (opening tag AND its
    # matching </section>). Counting opening tags alone lets a truncated final
    # slide — cut off mid-generation with no closing tag — pass as "present",
    # which both skips this fallback and (via check #4 above) gets its
    # dangling content silently deleted as trailing junk.
    slides = re.findall(r'<section[^>]+class="[^"]*slide[^"]*"[^>]*>.*?</section>', html, re.DOTALL)
    n_slides = len(slides)
    has_last_slide_hot_take = bool(slides) and "hot-take" in slides[-1]
    if n_slides < 7:
        # Entire slide 7 is missing — insert full fallback before </body>
        html = html.replace("</body>", SLIDE7_FALLBACK + "\n</body>")
        fixes.append(f"Injected missing Slide 7 (only {n_slides} complete slides found)")
    elif not has_last_slide_hot_take:
        # Slide 7 exists but hot-take section was truncated — add it inside last slide
        last_section_end = html.rfind("</section>")
        if last_section_end != -1:
            insert_pos = html.rfind("</div>", 0, last_section_end)
            if insert_pos != -1:
                html = html[:insert_pos] + HOT_TAKE_FALLBACK + "\n" + html[insert_pos:]
                fixes.append("Injected missing hot-take section into slide 7")

    # ── 6. Nav JS: ensure IntersectionObserver block is present ─────────────
    if "IntersectionObserver" not in html:
        html = html.replace("</body>", NAV_JS + "\n</body>")
        fixes.append("Injected missing nav JS (IntersectionObserver)")

    # ── 7. Cover h1: enforce Noto Sans SC weight 900, strip inner font overrides
    # Syne numerals look jarring next to Chinese — h1 must use Noto Sans SC 900
    html = re.sub(
        r"(h1\s*\{[^}]*?)font-family:\s*'Syne'[^;]*;",
        r"\1font-family: 'Noto Sans SC', sans-serif;",
        html
    )
    html = re.sub(
        r"(h1\s*\{[^}]*?)font-weight:\s*8\d\d;",
        r"\1font-weight: 900;",
        html
    )
    # Strip any font-family overrides inside the h1 element itself
    h1_match = re.search(r'(<h1[^>]*>)(.*?)(</h1>)', html, re.DOTALL | re.IGNORECASE)
    if h1_match:
        h1_inner = h1_match.group(2)
        fixed_inner = re.sub(r"(style=['\"][^'\"]*?)font-family:[^;'\"]+;?\s*", r"\1", h1_inner)
        fixed_inner = re.sub(r'\s*style=[\'\"]\s*[\'\"]\s*', '', fixed_inner)
        if fixed_inner != h1_inner:
            html = html[:h1_match.start(2)] + fixed_inner + html[h1_match.end(2):]
            fixes.append("Removed font-family overrides inside cover h1")
    h1_css_match = re.search(r'h1\s*\{[^}]*\}', html, re.DOTALL)
    if h1_css_match and "Noto Sans SC" not in h1_css_match.group(0):
        fixes.append("Enforced Noto Sans SC 900 on h1 (was Syne)")

    # ── 8. Nav dots: ensure Chinese titles ──────────────────────────────────
    en_titles = ['"Cover"', '"Match Report"', '"League Standing"',
                 '"Points Race"', '"Title Race"', '"Upcoming Fixtures"', '"Team News"']
    zh_titles = ['"封面"', '"本周战报"', '"积分榜"', '"积分追逐战"', '"积分竞争"', '"近期赛程"', '"球队动态"']
    for en, zh in zip(en_titles, zh_titles):
        if en in html:
            html = html.replace(en, zh)
            fixes.append(f"Fixed nav dot title {en} → {zh}")

    # ── 9. Crest watermark: fix truncated img tags missing closing > ─────────
    # Pattern: <img src="...t3@x2.png"\n  (line ends at quote, no closing >)
    # Fix: append onerror + class + alt + > to complete the tag
    CREST_URL = "https://resources.premierleague.com/premierleague/badges/t3@x2.png"
    broken_pattern = re.compile(
        r'(<img\s[^>]*?' + re.escape(CREST_URL) + r'")\s*\n(\s*<)',
        re.DOTALL
    )
    def fix_broken_crest(m):
        tag_open = m.group(1)
        next_tag = m.group(2)
        # If this is the cover crest (has class="cover-crest" or is a multiline img block), skip
        if 'crest-watermark' in tag_open or 'cover-crest' in tag_open:
            return m.group(0)
        return tag_open + ' onerror="this.style.display=\'none\'" class="crest-watermark" alt="">\n' + next_tag
    fixed_html = broken_pattern.sub(fix_broken_crest, html)
    if fixed_html != html:
        html = fixed_html
        fixes.append("Fixed truncated crest watermark img tags (missing closing >)")

    # ── 10. Cover crest: ensure src is present ───────────────────────────────
    cover_crest_no_src = re.search(
        r'<img\s+(?!.*src=)[^>]*class=["\']cover-crest["\'][^>]*>',
        html, re.DOTALL
    )
    if cover_crest_no_src:
        html = html.replace(
            cover_crest_no_src.group(0),
            cover_crest_no_src.group(0).replace(
                'class="cover-crest"',
                f'src="{CREST_URL}" onerror="this.style.display=\'none\'" class="cover-crest"'
            ).replace(
                "class='cover-crest'",
                f"src='{CREST_URL}' onerror=\"this.style.display='none'\" class='cover-crest'"
            )
        )
        fixes.append("Added missing src to cover crest img")

    # ── 11. Cover h1 size: enforce clamp(2.8rem,5.5vw,5rem) line-height 1.05 ─
    html = re.sub(
        r"(h1\s*\{[^}]*?)font-size\s*:\s*clamp\([^)]+\)\s*;",
        r"\1font-size: clamp(2.8rem,5.5vw,5rem);",
        html
    )
    html = re.sub(
        r"(h1\s*\{[^}]*?)line-height\s*:\s*[0-9.]+\s*;",
        r"\1line-height: 1.05;",
        html
    )

    # ── 12. Standings table sanity & ESPN cross-check ───────────────────────
    # Parse the rendered .pl-table and verify P = W+D+L per row, plus that
    # the rendered numbers match the ESPN ground-truth (if provided).
    table_match = re.search(r'<table class="pl-table">(.+?)</table>', html, re.DOTALL)
    if table_match:
        body = re.search(r'<tbody[^>]*>(.+?)</tbody>', table_match.group(1), re.DOTALL)
        rows_html = body.group(1) if body else table_match.group(1)
        tr_blocks = re.findall(r'<tr[^>]*>(.*?)</tr>', rows_html, re.DOTALL)
        parsed_rows: list[tuple] = []
        for tr in tr_blocks:
            cells = [
                re.sub(r'<[^>]+>', '', c).strip()
                for c in re.findall(r'<td[^>]*>(.*?)</td>', tr, re.DOTALL)
            ]
            # Expected order: rank, team, P, W, D, L, GD, Pts, [form pills]
            if len(cells) < 8:
                continue
            try:
                rank = int(re.sub(r'\D', '', cells[0]) or "0")
                p = int(cells[2]); w = int(cells[3])
                d = int(cells[4]); l = int(cells[5])
                pts = int(cells[7])
            except ValueError:
                continue
            team_label = cells[1]
            parsed_rows.append((rank, team_label, p, w, d, l, pts))
            # Per-row arithmetic
            if w + d + l != p:
                warnings.append(
                    f"Row {rank} ({team_label}): P={p} but W+D+L={w+d+l}"
                )

        # Top-2 P difference must be ≤ 1 (one game in hand max)
        if len(parsed_rows) >= 2:
            diff = abs(parsed_rows[0][2] - parsed_rows[1][2])
            if diff > 1:
                warnings.append(
                    f"Top-2 difference in matches played is {diff} "
                    f"(expected ≤ 1 — likely error)"
                )

        # Cross-check against ESPN ground truth row-by-row
        if espn_standings:
            for rendered, truth in zip(parsed_rows, espn_standings):
                _, label, rp, rw, rd, rl, rpts = rendered
                if (rp, rw, rd, rl, rpts) != (truth["p"], truth["w"],
                                              truth["d"], truth["l"],
                                              truth["pts"]):
                    warnings.append(
                        f"Row '{label}' diverges from ESPN: "
                        f"rendered P={rp} W={rw} D={rd} L={rl} Pts={rpts}, "
                        f"ESPN P={truth['p']} W={truth['w']} D={truth['d']} "
                        f"L={truth['l']} Pts={truth['pts']}"
                    )

    # ── Report ───────────────────────────────────────────────────────────────
    if fixes:
        print(f"  [validate] Applied {len(fixes)} fix(es):")
        for f in fixes:
            print(f"    • {f}")
    else:
        print("  [validate] All checks passed — no fixes needed.")

    if warnings:
        print(f"  [validate] {len(warnings)} WARNING(S) — manual review recommended:")
        for w in warnings:
            print(f"    ⚠ {w}", file=sys.stderr)

    return html


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    # Pre-fetch ground-truth PL standings from ESPN so the LLM doesn't have to
    # extract numbers from web_search prose. Falls back gracefully on failure.
    prompt = PROMPT
    espn_standings: list[dict] | None = None
    try:
        espn_standings = fetch_espn_standings(top_n=5)
        print("Fetched ESPN standings (top 5):")
        for s in espn_standings:
            print(f"  #{s['rank']:>2} {s['team_en']:<20} P={s['p']} "
                  f"W={s['w']} D={s['d']} L={s['l']} GD={s['gd']:>4} Pts={s['pts']}")
        prompt = build_standings_prompt_block(espn_standings) + PROMPT
    except Exception as e:
        print(f"WARNING: Failed to fetch ESPN standings ({e}); "
              f"falling back to web_search-only extraction.", file=sys.stderr)

    raw = generate_slides(prompt)
    html = extract_html(raw)
    html = dedupe_html(html)
    html = sanitise_html(html)
    html = validate_and_fix(html, espn_standings)

    os.makedirs(os.path.dirname(PAGES_FILE), exist_ok=True)

    with open(PAGES_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved: {PAGES_FILE}")
    print(f"Size:  {len(html):,} bytes")


if __name__ == "__main__":
    main()
