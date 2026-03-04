"""
Arsenal Weekly Slides Generator
Calls the Anthropic API (claude-sonnet-4-6 + web_search) to fetch the latest
Arsenal FC data and generate a self-contained Stadium Lights HTML slide deck.

Outputs:
  - docs/arsenal-weekly.html  (committed + pushed to GitHub Pages)
"""

import anthropic
import os
import re
import sys
import time

REPO_DIR   = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PAGES_FILE = os.path.join(REPO_DIR, "docs", "arsenal-weekly.html")

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
If a stat can only be found from one source, mark it "(待核实)".**

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
- Note expected return timeline only if a source explicitly states it — otherwise write "待定"
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
- Format as two JS arrays: labels (GW1, GW2…), arsenalPts[], rivalPts[]

**⑧ Goals Form Data (for chart)**
- Fetch Arsenal's last 8 matches: date, opponent, goals scored, goals conceded
- Source: flashscore.com or sofascore.com
- Format as JS arrays: matchLabels[] (opponent abbreviation), goalsFor[], goalsAgainst[]

---

Now generate a self-contained, full-screen scroll-snap HTML slide deck (8 slides) summarising
the week in Arsenal. Use the **Stadium Lights theme** with the exact design spec below.
**All text content must be in Chinese (Simplified). Output only the HTML — no markdown, no code fences.**

**Design theme — Stadium Lights (preserve exactly):**

CSS variables:
  --bg: #080b10
  --red: #EF0107
  --red-dim: rgba(239,1,7,0.15)
  --red-glow: rgba(239,1,7,0.35)
  --gold: #D4AF37
  --gold-dim: rgba(212,175,55,0.15)
  --text: #f0ede8
  --text-muted: rgba(240,237,232,0.5)

Fonts (load via Google Fonts):
  Syne 600–800 (display/headings)
  Noto Sans SC 300–700 (Chinese body)
  Oswald 400–700 (standalone stats/scores only — e.g. "3-1" score displays)
  IMPORTANT: Never apply Oswald to numbers embedded inside Chinese text (e.g. "第2名", "第3轮"). Use Noto Sans SC for all mixed Chinese+number text.

Chart.js (CDN): https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js

Layout:
  scroll-snap-type: y mandatory
  Each .slide = 100vw × 100dvh, scroll-snap-align: start
  overflow-y: scroll on html/body

Background FX on every slide:
  .beams — 4 red light beams swaying from top (beamSway keyframe)
  .pitch-bg — subtle grid at bottom 30%
  .center-glow — radial red gradient from top-center

Crest watermark on every slide:
  <img src="https://resources.premierleague.com/premierleague/badges/100/t3.png"
       onerror="this.style.display='none'" class="crest-watermark">
  opacity: 0.04, positioned right side, pointer-events: none

Typography (all clamp):
  title: clamp(2.2rem, 6vw, 5rem)
  h2: clamp(1.5rem, 3.5vw, 2.75rem)
  body: clamp(0.78rem, 1.3vw, 1rem)

.tag component: uppercase, letter-spacing 0.25em, color var(--red), ::before = 18px red horizontal line

Cards:
  background: rgba(255,255,255,0.04)
  border: 1px solid var(--red-dim)
  border-radius: 8px

Nav dots: fixed right side, active = var(--red), inactive = var(--text-muted)

Animations: fadeUp reveal on slide content entry; beamSway on light beams

**Slide structure (8 slides, all content in Chinese):**

Slide 1 — 封面 (Cover):
  Arsenal crest image (t3.png), large title "阿森纳本周快报", current date in Chinese,
  one-line TL;DR of the week in Chinese

Slide 2 — 本周战报 (Match Results):
  Last 1–2 results — score, competition, key goalscorers, brief tactical note.
  Use large score display with Oswald font.

Slide 3 — 积分榜 (League Standing):
  PL table showing top 5 teams — Arsenal row highlighted with red background tint.
  Columns: 排名, 球队, 赛, 胜, 平, 负, 净, 积分
  W/D/L form pills for last 5 (W=#22c55e, D=#f59e0b, L=#ef4444)
  Points gap to 2nd noted below table.

Slide 4 — 积分竞赛图 (Points Race Chart):
  Chart.js line chart using data from step ⑦, two datasets:
  - 阿森纳: borderColor #EF0107, backgroundColor rgba(239,1,7,0.1), fill true
  - 追赶者 (current 2nd-place team name): borderColor #D4AF37, backgroundColor transparent, fill false, borderDash [6,3]
  Both lines: borderWidth 2.5, pointRadius 3, pointHoverRadius 6, pointBackgroundColor matching borderColor, tension 0.3
  X-axis: gameweek labels (GW1, GW2…). Y-axis: cumulative points, position "right".
  Chart layout must NOT overflow the slide — see Chart.js layout spec below.
  Points gap shown as a styled <p> tag below the legend, not inside canvas.

Slide 5 — 积分竞争 (Title Race Rival):
  Current 2nd-place team spotlight — their last 3 results with scores,
  next 2–3 fixtures with difficulty colour (green=easy/amber=medium/red=hard),
  points gap, one-line threat verdict in Chinese.

Slide 6 — 近期赛程 (Upcoming Fixtures):
  Next 2–3 Arsenal fixtures — opponent, date, competition,
  difficulty stars (★☆☆–★★★), what's at stake. All in Chinese.

Slide 7 — 进攻数据图 (Goals Form Chart):
  Chart.js grouped bar chart using data from step ⑧, two datasets:
  - 进球 (Goals Scored): backgroundColor #EF0107, hoverBackgroundColor rgba(239,1,7,0.8)
  - 失球 (Goals Conceded): backgroundColor rgba(212,175,55,0.7), hoverBackgroundColor rgba(212,175,55,0.9)
  Both bars: borderRadius 4, borderSkipped false
  X-axis: matchLabels[] (opponent abbreviations). Y-axis: goals integer ticks, position "left".
  Reference lines: implement as two additional type:"line" datasets (not a plugin) —
    one at y=avgGoalsFor (dotted red), one at y=avgGoalsAgainst (dotted gold), pointRadius 0, borderWidth 1.
  Chart layout must NOT overflow the slide — see Chart.js layout spec below.

Slide 8 — 球队动态与总结 (Team News & Hot Take):
  Injury/suspension bullet cards, then a bold Hot Take paragraph on Arsenal's
  title chances. All in Chinese.

**Chart.js layout & styling rules (apply to both chart slides):**

Viewport fitting — CRITICAL (no slide may scroll):
- Give both chart slide <section> elements class="chart-slide"
- Inside the slide, use a flex-column layout: tag + h2 are flex:0 auto; the card is flex:1 1 0 with min-height:0 so it fills remaining space
- The canvas wrapper: position:relative; height:clamp(160px,42vh,360px); flex:1 1 0; min-height:0
- Add @media (max-height:700px) reducing canvas-wrap height to clamp(120px,38vh,260px)
- canvas element: width:100%!important; height:100%!important; display:block
- Card container: background rgba(255,255,255,0.04); border 1px solid rgba(239,1,7,0.15); border-radius 8px; overflow:hidden

Chart.js config (both charts):
- responsive:true, maintainAspectRatio:false (required for height-constrained wrapper)
- animation: duration 800, easing "easeOutQuart"
- plugins.legend.display:false — use a custom HTML legend instead
- Tooltip: bg rgba(8,11,16,0.95), border rgba(239,1,7,0.4) 1px, title/body color #f0ede8, cornerRadius 6, titleFont Oswald 13px, bodyFont Noto Sans SC 12px
- Both axes: grid.color rgba(255,255,255,0.05), grid.drawBorder false, border.display false, ticks.color rgba(240,237,232,0.5), ticks.font Oswald 11px, ticks.maxTicksLimit 10

Custom HTML legend: a flex row below the canvas-wrap with 10px coloured dots (border-radius 50%) and Noto Sans SC 0.75rem labels in rgba(240,237,232,0.7). For reference-line entries use a 16×2px rectangle dot instead of a circle.

Slide 4 annotation: one line below legend — Oswald 0.8rem rgba(240,237,232,0.5) — showing "▲ 领先 X 分" (red) or "▼ 落后 X 分" (gold).
Slide 7 annotation: two inline spans — "均进 X.X" red, "均失 X.X" gold — Oswald 0.8rem.

**Important:**
- The output must be a single complete HTML document starting with <!DOCTYPE html> and ending with </html>
- No markdown, no code fences, no commentary — raw HTML only
- All slide content in Simplified Chinese
- Embed everything inline (no external CSS files, no external JS files except Google Fonts CDN and Chart.js CDN)
- Load Chart.js from: https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js
- IMPORTANT: Initialise each chart with an inline <script> tag placed IMMEDIATELY after that slide's closing </section> tag — NOT in a DOMContentLoaded block at the end of the document. This ensures the chart JS is output early and survives any token truncation.
- Add class="chart-slide" to the <section> elements for Slides 4 and 7 so the chart layout CSS applies
- NEVER use a fixed pixel height on .slide — every slide must remain height:100vh; height:100dvh; overflow:hidden
- Both chart canvases MUST have their wrapper div constrained to clamp(160px,42vh,360px) so they never cause overflow
"""

# ── Agentic loop ───────────────────────────────────────────────────────────────

def generate_slides() -> str:
    """Call Claude with web_search in an agentic loop; return full HTML string."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = [{"role": "user", "content": PROMPT}]

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


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("ERROR: ANTHROPIC_API_KEY environment variable not set.", file=sys.stderr)
        sys.exit(1)

    raw = generate_slides()
    html = extract_html(raw)

    os.makedirs(os.path.dirname(PAGES_FILE), exist_ok=True)

    with open(PAGES_FILE, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"Saved: {PAGES_FILE}")
    print(f"Size:  {len(html):,} bytes")


if __name__ == "__main__":
    main()
