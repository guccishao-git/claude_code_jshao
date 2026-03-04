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

---

Now generate a self-contained, full-screen scroll-snap HTML slide deck (6 slides) summarising
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

**Slide structure (6 slides, all content in Chinese):**

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

Slide 4 — 积分竞争 (Title Race Rival):
  Current 2nd-place team spotlight — their last 3 results with scores,
  next 2–3 fixtures with difficulty colour (green=easy/amber=medium/red=hard),
  points gap, one-line threat verdict in Chinese.

Slide 5 — 近期赛程 (Upcoming Fixtures):
  Next 2–3 Arsenal fixtures — opponent, date, competition,
  difficulty stars (★☆☆–★★★), what's at stake. All in Chinese.

Slide 6 — 球队动态与总结 (Team News & Hot Take):
  Injury/suspension bullet cards, then a bold Hot Take paragraph on Arsenal's
  title chances. All in Chinese.

**Important:**
- The output must be a single complete HTML document starting with <!DOCTYPE html> and ending with </html>
- No markdown, no code fences, no commentary — raw HTML only
- All slide content in Simplified Chinese
- Embed everything inline (no external CSS files, no external JS files except Google Fonts CDN)
"""

# ── Agentic loop ───────────────────────────────────────────────────────────────

def generate_slides() -> str:
    """Call Claude with web_search in an agentic loop; return full HTML string."""
    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

    messages = [{"role": "user", "content": PROMPT}]

    print("Starting Arsenal weekly slides generation…")

    iteration = 0
    while True:
        iteration += 1
        print(f"  API call #{iteration} (stop_reason pending)…")

        response = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=16000,
            tools=[{"type": "web_search_20250305", "name": "web_search"}],
            messages=messages,
        )

        print(f"  stop_reason={response.stop_reason}")

        # Check what's in the response content
        has_tool_use = any(block.type == "tool_use" for block in response.content)
        text_parts = [block.text for block in response.content if hasattr(block, "text")]
        text = "\n".join(text_parts)

        if response.stop_reason == "end_turn":
            return text

        if response.stop_reason == "max_tokens":
            # If there are tool_use blocks, continue the agentic loop
            if has_tool_use:
                print("  max_tokens hit during tool_use, continuing loop…")
            elif text.strip():
                # Got truncated HTML — return what we have
                print("  max_tokens hit during HTML generation, extracting partial HTML…")
                return text
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

    match = re.search(r"(<!DOCTYPE html>.*</html>)", raw, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # Fallback: if no doctype, return everything
    if "<html" in raw.lower():
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
