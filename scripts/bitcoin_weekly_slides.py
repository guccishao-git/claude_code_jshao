"""
Bitcoin Weekly Slides Generator
Reads the last 7 days of digest .md files from ~/Documents/BitCoinNewsDaily/,
aggregates prices / forecasts / news, and generates a neon-cyber HTML slideshow.

Outputs:
  - docs/bitcoin-weekly.html  (committed + pushed to GitHub Pages)
  - ~/Documents/BitCoinNewsDaily/bitcoin-weekly-YYYY-Www.html  (local archive copy)
"""

import os
import re
import glob
import datetime
import subprocess
import shutil

try:
    import requests as _requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

DIGEST_DIR = os.path.expanduser("~/Documents/BitCoinNewsDaily")
REPO_DIR   = os.path.expanduser("~/Documents/GitHub1/claude_code_jshao")
PAGES_FILE = os.path.join(REPO_DIR, "docs", "bitcoin-weekly.html")


# ── 1. Parse digest files ─────────────────────────────────────────────────────

def parse_digest(filepath):
    """Extract date, price, forecasts, news, and plain-language summary."""
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    fname = os.path.basename(filepath)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
    if not date_match:
        return None
    date = datetime.date.fromisoformat(date_match.group(1))

    # ── Price ─────────────────────────────────────────────────────────────
    actual_price = None

    # Chinese table format: | 当前价格 | **$65,600** |
    m = re.search(r"\|\s*\*?\*?当前价格\*?\*?\s*\|\s*\*?\*?\$\s*([\d,]+)", content)
    if m:
        actual_price = float(m.group(1).replace(",", ""))

    # Chinese metric table: | **价格（USD）** | $67,811 |
    if actual_price is None:
        m = re.search(r"\|\s*\*\*价格[（(]USD[）)]\*\*\s*\|\s*\*?\*?\$\s*([\d,]+)", content)
        if m:
            actual_price = float(m.group(1).replace(",", ""))

    # English table: | Price (USD) | **$67,341** |
    if actual_price is None:
        m = re.search(r"\|\s*\*?\*?Price[^|]*\|\s*\*?\*?\$\s*([\d,]+)", content)
        if m:
            actual_price = float(m.group(1).replace(",", ""))

    # Fallback: first 5-digit dollar amount in a table row
    if actual_price is None:
        for line in content.splitlines():
            if "|" in line:
                m = re.search(r"\|\s*\*?\*?\$\s*([\d,]{5,})\s*\*?\*?\s*\|", line)
                if m:
                    actual_price = float(m.group(1).replace(",", ""))
                    break

    # ── 24h change ────────────────────────────────────────────────────────
    change_24h = None
    m = re.search(r"24小时涨跌幅[^\n]*?([+-]?\d+\.?\d*)\s*%", content)
    if m:
        change_24h = float(m.group(1))
    if change_24h is None:
        m = re.search(r"\|\s*\*?\*?24[^|]*\|\s*\*?\*?([+-]?\d+\.?\d*)\s*%", content)
        if m:
            change_24h = float(m.group(1))
    # Look for ↓ marker meaning negative
    if change_24h is not None:
        if "↓" in content[max(0, content.find(str(abs(change_24h)))-5):content.find(str(abs(change_24h)))+20]:
            change_24h = -abs(change_24h)

    # ── Forecasts ─────────────────────────────────────────────────────────
    forecasts = {}

    def parse_forecast_line(pattern):
        m = re.search(pattern, content, re.IGNORECASE)
        if not m:
            return None, None
        line = m.group(0)
        # target ± margin
        pm = re.search(r"\$([\d,]+)\s*[±]\s*\$?([\d,]+)", line)
        if pm:
            target = float(pm.group(1).replace(",", ""))
            margin = float(pm.group(2).replace(",", ""))
            return f"${target:,.0f} ± ${margin:,.0f}", (target - margin, target + margin)
        # low–high range
        rng = re.search(r"\$([\d,]+)[^\d$]+\$([\d,]+)", line)
        if rng:
            lo = float(rng.group(1).replace(",", ""))
            hi = float(rng.group(2).replace(",", ""))
            return f"${lo:,.0f} – ${hi:,.0f}", (lo, hi)
        sv = re.search(r"\$([\d,]+)", line)
        if sv:
            v = float(sv.group(1).replace(",", ""))
            return f"${v:,.0f}", (v, v)
        return None, None

    label_1w, range_1w = parse_forecast_line(r"(?:\*\*1周\*\*|1\s*Week)[^\n]+")
    label_1m, range_1m = parse_forecast_line(r"(?:\*\*1个月\*\*|1\s*Month)[^\n]+")

    # Year-end
    def parse_price_token(s):
        s = s.replace(",", "").strip()
        if s.upper().endswith("K"):
            return float(s[:-1]) * 1000
        return float(s)

    year_match = re.search(
        r"(?:1\s*Year|年底\d{4}[（\(]?主流|年底\d{4})[^\n]*?\$([\d,K]+)[^\n–\-]*?[\-–]\s*\$([\d,K]+)",
        content, re.IGNORECASE
    )
    label_1y = None
    if year_match:
        lo = parse_price_token(year_match.group(1))
        hi = parse_price_token(year_match.group(2))
        label_1y = f"${lo/1000:.0f}K – ${hi/1000:.0f}K"

    forecasts = {
        "1w": label_1w,
        "1m": label_1m,
        "1y": label_1y,
        "1w_range": range_1w,
        "1m_range": range_1m,
    }

    # ── News items ────────────────────────────────────────────────────────
    news_items = []
    # Match bold headlines like **📉 ETF资金持续外流**
    for m in re.finditer(r"\*\*([^\*\n]{5,80})\*\*\n([^\n#]{20,300})", content):
        title = m.group(1).strip()
        body  = m.group(2).strip()
        # Skip table rows and forecast lines
        if "|" in title or "$" in title[:3]:
            continue
        news_items.append({"title": title, "body": body})
        if len(news_items) >= 4:
            break

    # ── Plain language summary ────────────────────────────────────────────
    plain_summary = ""
    m = re.search(r"白话总结[^\n]*\n+\*\*[^\*\n]*\*\*\n+([^\n#]{30,})", content)
    if m:
        plain_summary = m.group(1).strip()
    if not plain_summary:
        # Fallback: grab any paragraph after "白话" heading
        m = re.search(r"白话[^\n]*\n+(.+?)(?:\n\n|\Z)", content, re.DOTALL)
        if m:
            plain_summary = m.group(1).strip()[:300]

    return {
        "date": date,
        "actual_price": actual_price,
        "change_24h": change_24h,
        "forecasts": forecasts,
        "news": news_items,
        "plain_summary": plain_summary,
        "file": fname,
    }


def load_week_digests(lookback_days=14):
    """Load digests from the past `lookback_days` days, return sorted by date."""
    today = datetime.date.today()
    cutoff = today - datetime.timedelta(days=lookback_days)
    files = sorted(glob.glob(os.path.join(DIGEST_DIR, "digest-*.md")))
    results = []
    for f in files:
        parsed = parse_digest(f)
        if parsed and parsed["actual_price"] and parsed["date"] >= cutoff:
            results.append(parsed)
    # Always return at most 7 most recent
    return results[-7:]


# ── 2. Fetch historical prices from CoinGecko ────────────────────────────────

def fetch_historical_prices(days=365):
    """Return list of (iso_date_str, price) for up to `days` days."""
    if not _HAS_REQUESTS:
        print("   ⚠️  requests not installed — skipping historical fetch.")
        return []
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    try:
        resp = _requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json().get("prices", [])
        result = []
        for ts_ms, price in data:
            dt = datetime.datetime.utcfromtimestamp(ts_ms / 1000).date()
            result.append((dt.isoformat(), round(price, 2)))
        return result
    except Exception as e:
        print(f"   ⚠️  CoinGecko fetch failed — {e}")
        return []


# ── 3. Build HTML slides ──────────────────────────────────────────────────────

def fmt_price(p):
    if p is None:
        return "N/A"
    return f"${p:,.0f}"

def fmt_change(c):
    if c is None:
        return "—"
    sign = "+" if c >= 0 else ""
    return f"{sign}{c:.1f}%"

def change_class(c):
    if c is None:
        return ""
    return "up" if c >= 0 else "down"


def build_html(digests, historical_prices=None):
    if not digests:
        raise ValueError("No digest data found.")

    first  = digests[0]
    latest = digests[-1]
    today  = datetime.date.today()

    week_num  = today.isocalendar()[1]
    year      = today.year
    date_from = first["date"].strftime("%m月%d日")
    date_to   = latest["date"].strftime("%m月%d日")

    open_price  = first["actual_price"]
    close_price = latest["actual_price"]
    weekly_pct  = ((close_price - open_price) / open_price * 100) if open_price else 0
    weekly_dir  = "up" if weekly_pct >= 0 else "down"
    weekly_sign = "+" if weekly_pct >= 0 else ""

    import json as _json

    # ── Historical price data (CoinGecko) ─────────────────────────────────
    # hist_prices: list of [iso_date, price] — full 1Y dataset for JS
    hist = historical_prices or []
    hist_labels = [r[0] for r in hist]   # ISO strings, used by JS for slicing
    hist_values = [r[1] for r in hist]

    # Digest marker overlay — dates + prices as parallel arrays
    digest_dates  = [d["date"].isoformat() for d in digests]
    digest_prices = [d["actual_price"]      for d in digests]

    # Forecast extension points (from latest digest)
    fc_ranges = latest["forecasts"]
    fc_points = []   # [{date, price, label}]
    if fc_ranges.get("1w_range"):
        mid = sum(fc_ranges["1w_range"]) / 2
        fc_points.append({
            "date":  (latest["date"] + datetime.timedelta(days=7)).isoformat(),
            "price": round(mid, 0),
            "label": "1W预测",
        })
    if fc_ranges.get("1m_range"):
        mid = sum(fc_ranges["1m_range"]) / 2
        fc_points.append({
            "date":  (latest["date"] + datetime.timedelta(days=30)).isoformat(),
            "price": round(mid, 0),
            "label": "1M预测",
        })

    hist_labels_js   = _json.dumps(hist_labels)
    hist_values_js   = _json.dumps(hist_values)
    digest_dates_js  = _json.dumps(digest_dates)
    digest_prices_js = _json.dumps(digest_prices)
    fc_points_js     = _json.dumps(fc_points)

    # Fallback Y range (used if no historical data)
    all_prices = [p for p in digest_prices if p]
    chart_min = int(min(all_prices) * 0.94) if all_prices else 50000
    chart_max = int(max(all_prices) * 1.06) if all_prices else 100000

    # Latest forecasts (from most recent digest that has them)
    fc_1w = fc_1m = fc_1y = "—"
    for d in reversed(digests):
        fc = d["forecasts"]
        if fc.get("1w") and fc_1w == "—":
            fc_1w = fc["1w"]
        if fc.get("1m") and fc_1m == "—":
            fc_1m = fc["1m"]
        if fc.get("1y") and fc_1y == "—":
            fc_1y = fc["1y"]
        if fc_1w != "—" and fc_1m != "—" and fc_1y != "—":
            break

    # Aggregate news (deduplicate by title prefix)
    all_news = []
    seen = set()
    for d in reversed(digests):
        for item in d["news"]:
            key = item["title"][:12]
            if key not in seen:
                all_news.append({**item, "date": d["date"].strftime("%m/%d")})
                seen.add(key)
            if len(all_news) >= 5:
                break
        if len(all_news) >= 5:
            break

    # Plain language summary from latest digest
    plain = latest.get("plain_summary", "")

    # Price journey rows
    price_rows_html = ""
    for d in digests:
        c = d.get("change_24h")
        cls = change_class(c)
        price_rows_html += f"""
        <tr>
          <td class="mono">{d['date'].strftime('%m/%d')}</td>
          <td class="mono accent">{fmt_price(d['actual_price'])}</td>
          <td class="mono {cls}">{fmt_change(c)}</td>
        </tr>"""

    # News cards HTML
    news_cards_html = ""
    for item in all_news[:4]:
        news_cards_html += f"""
        <div class="news-card reveal">
          <div class="news-date mono">{item['date']}</div>
          <div class="news-title">{item['title']}</div>
          <div class="news-body">{item['body'][:180]}</div>
        </div>"""

    generated_at = today.strftime("%Y-%m-%d")

    html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>比特币周报 W{week_num} · {year}</title>

  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@300;400;500;600;700&family=Space+Mono:ital,wght@0,400;0,700;1,400&display=swap" rel="stylesheet">
  <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>

  <style>
    /* ═══════════════════════════════════════
       NEON CYBER THEME
       ═══════════════════════════════════════ */
    :root {{
      --bg-primary:    #050a14;
      --bg-secondary:  #0a1526;
      --bg-card:       rgba(255,255,255,0.04);
      --cyan:          #00ffc8;
      --cyan-dim:      rgba(0,255,200,0.15);
      --cyan-glow:     rgba(0,255,200,0.35);
      --magenta:       #ff00b4;
      --magenta-dim:   rgba(255,0,180,0.12);
      --red:           #ff5060;
      --red-dim:       rgba(255,80,96,0.12);
      --amber:         #ffb340;
      --text-primary:  #e8f4f8;
      --text-muted:    rgba(232,244,248,0.45);
      --text-dim:      rgba(232,244,248,0.25);
      --font-display:  'Space Grotesk', sans-serif;
      --font-mono:     'Space Mono', monospace;
      --fs-title:  clamp(2.2rem, 5.5vw, 4.5rem);
      --fs-h2:     clamp(1.5rem, 3.5vw, 2.75rem);
      --fs-h3:     clamp(1rem,   2vw,   1.5rem);
      --fs-body:   clamp(0.78rem, 1.3vw, 1rem);
      --fs-small:  clamp(0.65rem, 1vw,   0.8rem);
      --fs-mono:   clamp(0.65rem, 1vw,   0.82rem);
      --fs-tag:    clamp(0.55rem, 0.85vw, 0.72rem);
      --pad:       clamp(1.5rem, 4vw, 4rem);
      --gap:       clamp(0.6rem, 1.5vw, 1.5rem);
      --gap-sm:    clamp(0.3rem, 0.8vw, 0.75rem);
      --border:    1px solid rgba(0,255,200,0.12);
      --border-red:1px solid rgba(255,80,96,0.2);
      --radius:    6px;
      --radius-lg: 12px;
      --ease-expo: cubic-bezier(0.16, 1, 0.3, 1);
      --dur:       0.65s;
    }}

    *, *::before, *::after {{ margin:0; padding:0; box-sizing:border-box; }}

    html {{
      height: 100%;
      scroll-snap-type: y mandatory;
      scroll-behavior: smooth;
      overflow-x: hidden;
    }}

    body {{
      font-family: var(--font-display);
      background: var(--bg-primary);
      color: var(--text-primary);
      height: 100%;
      overflow-x: hidden;
    }}

    /* ── SLIDE ── */
    .slide {{
      width: 100vw;
      height: 100vh;
      height: 100dvh;
      overflow: hidden;
      scroll-snap-align: start;
      display: flex;
      flex-direction: column;
      justify-content: center;
      position: relative;
      padding: var(--pad);
    }}

    .slide-content {{
      position: relative;
      z-index: 2;
      flex: 1;
      display: flex;
      flex-direction: column;
      justify-content: center;
      max-height: 100%;
      overflow: hidden;
    }}

    /* ── BACKGROUND DECORATION ── */
    .grid-bg {{
      position: absolute; inset: 0;
      background-image:
        linear-gradient(rgba(0,255,200,0.035) 1px, transparent 1px),
        linear-gradient(90deg, rgba(0,255,200,0.035) 1px, transparent 1px);
      background-size: 60px 60px;
      pointer-events: none; z-index: 0;
      animation: gridPulse 5s ease-in-out infinite;
    }}
    @keyframes gridPulse {{ 0%,100%{{opacity:.6}} 50%{{opacity:1}} }}

    .glow-cyan {{
      position: absolute;
      width: clamp(300px,40vw,600px); height: clamp(300px,40vw,600px);
      background: radial-gradient(circle, rgba(0,255,200,0.12) 0%, transparent 70%);
      top: calc(-1 * clamp(80px,12vw,150px));
      right: calc(-1 * clamp(80px,12vw,150px));
      pointer-events: none; z-index: 0;
      animation: driftA 7s ease-in-out infinite;
    }}
    .glow-magenta {{
      position: absolute;
      width: clamp(200px,30vw,450px); height: clamp(200px,30vw,450px);
      background: radial-gradient(circle, rgba(255,0,180,0.08) 0%, transparent 70%);
      bottom: calc(-1 * clamp(50px,8vw,100px));
      left: calc(-1 * clamp(50px,8vw,100px));
      pointer-events: none; z-index: 0;
      animation: driftB 9s ease-in-out infinite;
    }}
    @keyframes driftA {{ 0%,100%{{transform:translate(0,0)}} 50%{{transform:translate(-25px,25px)}} }}
    @keyframes driftB {{ 0%,100%{{transform:translate(0,0)}} 50%{{transform:translate(20px,-20px)}} }}

    .corner {{
      position: absolute;
      width: clamp(24px,3vw,44px); height: clamp(24px,3vw,44px);
      border-color: rgba(0,255,200,0.3); border-style: solid; z-index: 1;
    }}
    .corner.tl {{ top: clamp(12px,2vw,24px); left: clamp(12px,2vw,24px); border-width: 2px 0 0 2px; }}
    .corner.br {{ bottom: clamp(12px,2vw,24px); right: clamp(12px,2vw,24px); border-width: 0 2px 2px 0; }}

    /* ── TYPOGRAPHY ── */
    .tag {{
      display: inline-flex; align-items: center; gap: 0.6rem;
      font-family: var(--font-mono); font-size: var(--fs-tag);
      letter-spacing: 0.25em; text-transform: uppercase;
      color: var(--cyan); margin-bottom: clamp(0.75rem,1.8vh,1.8rem);
    }}
    .tag::before {{
      content: ''; display: inline-block; width: 16px; height: 1px;
      background: var(--cyan); opacity: 0.6;
    }}

    h1 {{ font-size: var(--fs-title); font-weight: 700; line-height: 1.05; letter-spacing: -0.02em; margin-bottom: clamp(0.5rem,1.2vh,1.2rem); }}
    h2 {{ font-size: var(--fs-h2);    font-weight: 700; line-height: 1.1;  letter-spacing: -0.02em; margin-bottom: clamp(0.5rem,1.2vh,1.2rem); }}

    .accent  {{ color: var(--cyan); }}
    .danger  {{ color: var(--red); }}
    .muted   {{ color: var(--text-muted); }}
    .up      {{ color: var(--cyan); }}
    .down    {{ color: var(--red); }}

    .subtitle {{
      font-size: var(--fs-body); color: var(--text-muted);
      line-height: 1.55; margin-bottom: clamp(0.75rem,1.5vh,1.5rem);
    }}

    .mono {{ font-family: var(--font-mono); font-size: var(--fs-mono); }}

    /* ── BADGE ── */
    .badge {{
      display: inline-flex; align-items: center; gap: 0.5rem;
      padding: 0.35rem 0.85rem; border-radius: var(--radius);
      font-family: var(--font-mono); font-size: var(--fs-mono);
      border: var(--border); background: var(--cyan-dim); color: var(--cyan);
    }}
    .badge.red {{ border: var(--border-red); background: var(--red-dim); color: var(--red); }}
    .badges {{ display: flex; flex-wrap: wrap; gap: 0.6rem; margin-top: clamp(0.75rem,1.5vh,1.5rem); }}
    .badge .dot {{
      width: 6px; height: 6px; border-radius: 50%;
      background: currentColor; box-shadow: 0 0 8px currentColor;
      animation: blink 1.8s ease-in-out infinite;
    }}
    @keyframes blink {{ 0%,100%{{opacity:1}} 50%{{opacity:.25}} }}

    /* ── CARD ── */
    .card {{
      background: var(--bg-card); border: var(--border);
      border-radius: var(--radius-lg); padding: clamp(0.75rem,1.5vw,1.5rem);
    }}

    /* ── PRICE TABLE (slide 2) ── */
    .price-table-wrap {{
      margin-top: clamp(0.6rem,1.5vh,1.5rem);
      overflow: hidden; border-radius: var(--radius-lg);
      border: var(--border);
    }}
    table {{
      width: 100%; border-collapse: collapse;
      font-size: var(--fs-body);
    }}
    thead th {{
      font-family: var(--font-mono); font-size: var(--fs-tag);
      letter-spacing: 0.15em; text-transform: uppercase;
      color: var(--text-muted); padding: clamp(0.4rem,0.8vh,0.75rem) clamp(0.6rem,1vw,1rem);
      background: rgba(255,255,255,0.03); border-bottom: 1px solid rgba(255,255,255,0.06);
      text-align: left;
    }}
    tbody tr {{
      border-bottom: 1px solid rgba(255,255,255,0.04);
      transition: background 0.15s ease;
    }}
    tbody tr:last-child {{ border-bottom: none; }}
    tbody tr:hover {{ background: rgba(0,255,200,0.03); }}
    tbody td {{
      padding: clamp(0.35rem,0.7vh,0.65rem) clamp(0.6rem,1vw,1rem);
    }}
    tbody td.mono {{ font-family: var(--font-mono); font-size: var(--fs-mono); }}
    tbody td.accent {{ color: var(--cyan); font-weight: 600; }}

    /* ── NEWS CARDS (slide 3) ── */
    .news-grid {{
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: var(--gap);
      margin-top: clamp(0.6rem,1.5vh,1.5rem);
    }}
    .news-card {{
      background: var(--bg-card); border: var(--border);
      border-radius: var(--radius-lg);
      padding: clamp(0.75rem,1.5vw,1.25rem);
      display: flex; flex-direction: column; gap: var(--gap-sm);
    }}
    .news-date {{
      font-family: var(--font-mono); font-size: var(--fs-tag);
      color: var(--cyan); letter-spacing: 0.15em;
    }}
    .news-title {{ font-size: var(--fs-h3); font-weight: 600; line-height: 1.2; }}
    .news-body  {{ font-size: var(--fs-small); color: var(--text-muted); line-height: 1.5; flex: 1; }}

    /* ── FORECAST CARDS (slide 4) ── */
    .forecast-grid {{
      display: grid;
      grid-template-columns: repeat(3, 1fr);
      gap: var(--gap);
      margin-top: clamp(0.6rem,1.5vh,1.5rem);
    }}
    .forecast-card {{
      background: var(--bg-card); border: var(--border);
      border-radius: var(--radius-lg);
      padding: clamp(0.75rem,1.5vw,1.5rem);
      display: flex; flex-direction: column; gap: var(--gap-sm);
    }}
    .forecast-card.highlight {{
      border-color: rgba(0,255,200,0.25); background: rgba(0,255,200,0.04);
    }}
    .fc-timeframe {{
      font-family: var(--font-mono); font-size: var(--fs-tag);
      letter-spacing: 0.2em; text-transform: uppercase; color: var(--cyan);
    }}
    .fc-price {{
      font-family: var(--font-mono);
      font-size: clamp(1.1rem,2.2vw,1.8rem);
      font-weight: 700; color: var(--text-primary); line-height: 1.1;
    }}
    .fc-note {{ font-size: var(--fs-small); color: var(--text-muted); line-height: 1.4; }}

    /* ── SUMMARY LIST (slide 5) ── */
    .summary-list {{
      display: flex; flex-direction: column;
      gap: var(--gap-sm);
      margin-top: clamp(0.5rem,1.2vh,1.2rem);
    }}
    .summary-item {{
      display: flex; gap: 0.8rem; align-items: flex-start;
      padding: clamp(0.5rem,1vw,0.85rem);
      background: var(--bg-card); border: var(--border);
      border-radius: var(--radius); font-size: var(--fs-body);
    }}
    .summary-item .s-icon {{ font-size: clamp(0.9rem,1.5vw,1.1rem); flex-shrink: 0; line-height: 1.4; }}
    .summary-item .s-text {{ color: var(--text-muted); line-height: 1.5; }}
    .summary-item .s-text strong {{ color: var(--text-primary); font-weight: 600; }}

    /* ── REVEAL ANIMATION ── */
    .reveal {{
      opacity: 0;
      transform: translateY(16px);
      animation: fadeUp var(--dur) var(--ease-expo) forwards;
    }}
    .d1 {{ animation-delay: 0.05s; }}
    .d2 {{ animation-delay: 0.15s; }}
    .d3 {{ animation-delay: 0.25s; }}
    .d4 {{ animation-delay: 0.35s; }}
    .d5 {{ animation-delay: 0.45s; }}
    @keyframes fadeUp {{
      to {{ opacity: 1; transform: translateY(0); }}
    }}

    /* ── NAV DOTS ── */
    #nav-dots {{
      position: fixed; right: clamp(12px,2vw,24px); top: 50%;
      transform: translateY(-50%);
      display: flex; flex-direction: column; gap: 8px; z-index: 100;
    }}
    .nav-dot {{
      width: 7px; height: 7px; border-radius: 50%;
      background: rgba(255,255,255,0.2); cursor: pointer;
      transition: background 0.25s, transform 0.25s;
    }}
    .nav-dot.active {{ background: var(--cyan); transform: scale(1.4); }}

    /* ── PROGRESS BAR ── */
    #progress-bar {{
      position: fixed; top: 0; left: 0; height: 2px;
      background: linear-gradient(90deg, var(--cyan), var(--magenta));
      z-index: 200; transition: width 0.3s ease;
    }}

    /* ── KBD HINT ── */
    #kbd-hint {{
      position: fixed; bottom: clamp(12px,2vh,20px); left: 50%;
      transform: translateX(-50%);
      font-family: var(--font-mono); font-size: var(--fs-tag);
      color: var(--text-dim); z-index: 100; white-space: nowrap;
      letter-spacing: 0.1em;
    }}

    /* ── CHART TOOLBAR ── */
    .chart-toolbar {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      flex-wrap: wrap;
      gap: 0.5rem;
      margin-top: clamp(0.3rem, 0.8vh, 0.75rem);
      margin-bottom: clamp(0.3rem, 0.6vh, 0.5rem);
    }}
    .chart-timeframes {{
      display: flex;
      gap: 0.4rem;
    }}
    .tf-btn {{
      font-family: var(--font-mono);
      font-size: var(--fs-tag);
      letter-spacing: 0.12em;
      padding: 0.3rem 0.75rem;
      border-radius: var(--radius);
      border: var(--border);
      background: transparent;
      color: var(--text-muted);
      cursor: pointer;
      transition: all 0.2s ease;
    }}
    .tf-btn:hover {{ color: var(--cyan); border-color: rgba(0,255,200,0.3); }}
    .tf-btn.active {{
      background: var(--cyan-dim);
      border-color: rgba(0,255,200,0.35);
      color: var(--cyan);
    }}

    /* ── CHART SLIDE ── */
    .chart-wrap {{
      position: relative;
      flex: 1;
      min-height: 0;
      margin-top: clamp(0.6rem, 1.5vh, 1.5rem);
      border: var(--border);
      border-radius: var(--radius-lg);
      background: rgba(0,255,200,0.02);
      padding: clamp(0.5rem, 1vw, 1rem);
    }}
    .chart-wrap canvas {{
      display: block;
      width: 100% !important;
      height: 100% !important;
    }}
    .chart-legend {{
      display: flex; gap: 1.2rem; flex-wrap: wrap;
      margin-top: clamp(0.4rem, 0.8vh, 0.75rem);
    }}
    .chart-legend-item {{
      display: flex; align-items: center; gap: 0.4rem;
      font-family: var(--font-mono); font-size: var(--fs-tag);
      color: var(--text-muted);
    }}
    .chart-legend-item .leg-dot {{
      width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0;
    }}

    /* ── RESPONSIVE ── */
    @media (max-width: 768px) {{
      .news-grid     {{ grid-template-columns: 1fr; }}
      .forecast-grid {{ grid-template-columns: 1fr; }}
    }}
    @media (max-height: 700px) {{
      :root {{ --pad: clamp(1rem,3vw,2.5rem); --gap: clamp(0.4rem,1vw,1rem); --fs-title: clamp(1.8rem,4.5vw,3.5rem); --fs-h2: clamp(1.2rem,2.8vw,2.2rem); }}
    }}
    @media (prefers-reduced-motion: reduce) {{
      *, *::before, *::after {{ animation-duration: 0.01ms !important; transition-duration: 0.2s !important; }}
      html {{ scroll-behavior: auto; }}
    }}
  </style>
</head>
<body>

  <div id="progress-bar"></div>
  <nav id="nav-dots"></nav>
  <div id="kbd-hint">↑ ↓ 或空格 导航</div>


  <!-- ════════════════════════════════════════
       SLIDE 1 — TITLE / 封面
       ════════════════════════════════════════ -->
  <section class="slide slide-title" id="slide-1" aria-label="封面">
    <div class="grid-bg"></div>
    <div class="glow-cyan"></div>
    <div class="glow-magenta"></div>
    <div class="corner tl"></div>
    <div class="corner br"></div>

    <div class="slide-content">
      <div class="tag reveal d1">BTC · 周报 · W{week_num} / {year}</div>
      <h1 class="reveal d2">
        比特币<br><span class="accent">每周回顾</span>
      </h1>
      <p class="subtitle reveal d3">{date_from} – {date_to} · 本周行情全回顾</p>
      <div class="badges reveal d4">
        <span class="badge"><span class="dot"></span>收盘价 &nbsp;{fmt_price(close_price)}</span>
        <span class="badge {'red' if weekly_pct < 0 else ''}">{'▼' if weekly_pct < 0 else '▲'} 周涨跌 {weekly_sign}{weekly_pct:.1f}%</span>
      </div>
    </div>
  </section>


  <!-- ════════════════════════════════════════
       SLIDE 2 — PRICE CHART / 价格走势图
       ════════════════════════════════════════ -->
  <section class="slide" id="slide-2" aria-label="价格走势图">
    <div class="grid-bg"></div>
    <div class="glow-cyan"></div>

    <div class="slide-content">
      <div class="tag reveal d1">价格走势图</div>
      <h2 class="reveal d2">BTC/USD <span class="accent">价格走势</span></h2>

      <div class="chart-toolbar reveal d2">
        <div class="chart-timeframes">
          <button class="tf-btn" data-days="7">1W</button>
          <button class="tf-btn active" data-days="30">1M</button>
          <button class="tf-btn" data-days="365">1Y</button>
        </div>
        <div class="chart-legend">
          <span class="chart-legend-item">
            <span class="leg-dot" style="background:#00ffc8;box-shadow:0 0 6px rgba(0,255,200,0.5);"></span>实际价格
          </span>
          <span class="chart-legend-item">
            <span class="leg-dot" style="background:#ffffff;border:2px solid #00ffc8;"></span>摘要记录
          </span>
          <span class="chart-legend-item">
            <span class="leg-dot" style="background:#ff00b4;box-shadow:0 0 6px rgba(255,0,180,0.4);"></span>预测中位数
          </span>
        </div>
      </div>

      <div class="chart-wrap reveal d3">
        <canvas id="priceChart"></canvas>
      </div>
    </div>
  </section>


  <!-- ════════════════════════════════════════
       SLIDE 3 — PRICE JOURNEY / 价格回顾
       ════════════════════════════════════════ -->
  <section class="slide" id="slide-3" aria-label="价格回顾">
    <div class="grid-bg"></div>
    <div class="glow-cyan"></div>

    <div class="slide-content">
      <div class="tag reveal d1">价格回顾</div>
      <h2 class="reveal d2">
        本周走势：
        <span class="accent">{fmt_price(open_price)}</span>
        →
        <span class="{'accent' if weekly_pct >= 0 else 'danger'}">{fmt_price(close_price)}</span>
      </h2>
      <p class="subtitle reveal d3">每日收盘价与涨跌幅</p>

      <div class="price-table-wrap reveal d4">
        <table>
          <thead>
            <tr>
              <th>日期</th>
              <th>价格 (USD)</th>
              <th>24h 涨跌</th>
            </tr>
          </thead>
          <tbody>
            {price_rows_html}
          </tbody>
        </table>
      </div>
    </div>
  </section>


  <!-- ════════════════════════════════════════
       SLIDE 4 — NEWS HIGHLIGHTS / 市场新闻
       ════════════════════════════════════════ -->
  <section class="slide" id="slide-4" aria-label="市场新闻">
    <div class="grid-bg"></div>
    <div class="glow-magenta"></div>

    <div class="slide-content">
      <div class="tag reveal d1">市场新闻</div>
      <h2 class="reveal d2">本周<span class="accent">重要事件</span></h2>
      <p class="subtitle reveal d3">影响行情的关键新闻汇总</p>

      <div class="news-grid reveal d4">
        {news_cards_html if news_cards_html else '<p class="muted">本周暂无收录新闻。</p>'}
      </div>
    </div>
  </section>


  <!-- ════════════════════════════════════════
       SLIDE 5 — FORECAST / 预测展望
       ════════════════════════════════════════ -->
  <section class="slide" id="slide-5" aria-label="预测展望">
    <div class="grid-bg"></div>
    <div class="glow-cyan"></div>

    <div class="slide-content">
      <div class="tag reveal d1">预测展望</div>
      <h2 class="reveal d2">下周 · 下月 · <span class="accent">年底目标</span></h2>
      <p class="subtitle reveal d3">基于最新摘要的价格预测（截至 {latest['date'].strftime('%m月%d日')}）</p>

      <div class="forecast-grid reveal d4">
        <div class="forecast-card highlight">
          <div class="fc-timeframe">1 周预测</div>
          <div class="fc-price">{fc_1w}</div>
          <div class="fc-note">短期目标价，波动区间较窄</div>
        </div>
        <div class="forecast-card">
          <div class="fc-timeframe">1 月预测</div>
          <div class="fc-price">{fc_1m}</div>
          <div class="fc-note">中期目标，参考宏观走势</div>
        </div>
        <div class="forecast-card">
          <div class="fc-timeframe">年底目标</div>
          <div class="fc-price">{fc_1y}</div>
          <div class="fc-note">机构共识宽区间，仅供参考</div>
        </div>
      </div>
    </div>
  </section>


  <!-- ════════════════════════════════════════
       SLIDE 6 — PLAIN SUMMARY / 白话总结
       ════════════════════════════════════════ -->
  <section class="slide" id="slide-6" aria-label="白话总结">
    <div class="grid-bg"></div>
    <div class="glow-magenta"></div>
    <div class="corner tl"></div>
    <div class="corner br"></div>

    <div class="slide-content">
      <div class="tag reveal d1">一句话总结</div>
      <h2 class="reveal d2">这周<span class="accent">说明了什么？</span></h2>

      <div class="summary-list reveal d3">
        <div class="summary-item">
          <span class="s-icon">{'📈' if weekly_pct >= 0 else '📉'}</span>
          <span class="s-text">
            <strong>本周表现：</strong>
            BTC 从 {fmt_price(open_price)} {'上涨' if weekly_pct >= 0 else '下跌'} 至 {fmt_price(close_price)}，
            周涨跌幅 <strong class="{'up' if weekly_pct >= 0 else 'down'}">{weekly_sign}{weekly_pct:.1f}%</strong>。
          </span>
        </div>
        <div class="summary-item">
          <span class="s-icon">🔮</span>
          <span class="s-text">
            <strong>下周展望：</strong>
            最新预测目标价 <strong>{fc_1w}</strong>，关注宏观数据与链上资金流向。
          </span>
        </div>
        {'<div class="summary-item"><span class="s-icon">💬</span><span class="s-text">' + plain + '</span></div>' if plain else ''}
      </div>

      <div class="muted mono reveal d5" style="margin-top: clamp(1rem,2vh,2rem); font-size: var(--fs-tag);">
        生成时间: {generated_at} &nbsp;·&nbsp; 数据来源: 每日摘要文件
      </div>
    </div>
  </section>


  <script>
    // ── Chart.js — Price Trend with 1W / 1M / 1Y toggle ─────────────────
    (function() {{
      // Full historical dataset (up to 1Y from CoinGecko)
      const histLabels = {hist_labels_js};   // ISO date strings
      const histValues = {hist_values_js};   // prices

      // Digest price markers
      const digestDates  = {digest_dates_js};
      const digestPrices = {digest_prices_js};

      // Forecast extension points
      const fcPoints = {fc_points_js};

      const fallbackMin = {chart_min};
      const fallbackMax = {chart_max};

      // ── Helpers ───────────────────────────────────────────────────────
      function sliceByDays(days) {{
        if (!histLabels.length) return {{ labels: [], values: [] }};
        const cutoff = new Date();
        cutoff.setDate(cutoff.getDate() - days);
        const idx = histLabels.findIndex(d => new Date(d) >= cutoff);
        const start = idx === -1 ? 0 : idx;
        return {{ labels: histLabels.slice(start), values: histValues.slice(start) }};
      }}

      // Add forecast points that fall within the view window
      function buildForecastDataset(viewLabels, viewValues) {{
        // Extend labels/values with forecast points beyond today
        const extended = {{ labels: [...viewLabels], values: [...viewValues] }};
        fcPoints.forEach(pt => {{
          if (!extended.labels.includes(pt.date)) {{
            extended.labels.push(pt.date);
            extended.values.push(null);   // no actual price
          }}
        }});
        // Build forecast series aligned to extended labels
        return extended.labels.map(lbl => {{
          const fc = fcPoints.find(p => p.date === lbl);
          return fc ? fc.price : null;
        }});
      }}

      // Build digest marker dataset aligned to chart labels
      function buildDigestDataset(viewLabels) {{
        return viewLabels.map(lbl => {{
          const idx = digestDates.indexOf(lbl);
          return idx !== -1 ? digestPrices[idx] : null;
        }});
      }}

      function yRange(values) {{
        const valid = values.filter(v => v !== null && v !== undefined);
        if (!valid.length) return {{ min: fallbackMin, max: fallbackMax }};
        return {{
          min: Math.floor(Math.min(...valid) * 0.95),
          max: Math.ceil(Math.max(...valid)  * 1.04),
        }};
      }}

      // ── Initial view: 1M ─────────────────────────────────────────────
      let current = sliceByDays(30);
      const fcSeries = buildForecastDataset(current.labels, current.values);
      const allExtLabels = current.labels.length + fcPoints.filter(p => !current.labels.includes(p.date)).length
        ? [...current.labels, ...fcPoints.filter(p => !current.labels.includes(p.date)).map(p => p.date)]
        : current.labels;

      const ctx = document.getElementById('priceChart').getContext('2d');

      // Cyan gradient fill
      const grad = ctx.createLinearGradient(0, 0, 0, 380);
      grad.addColorStop(0, 'rgba(0,255,200,0.22)');
      grad.addColorStop(1, 'rgba(0,255,200,0.01)');

      const initRange = yRange([...current.values, ...fcSeries.filter(Boolean)]);

      const chart = new Chart(ctx, {{
        type: 'line',
        data: {{
          labels: current.labels,
          datasets: [
            {{
              label: '实际价格',
              data: current.values,
              borderColor: '#00ffc8',
              borderWidth: 2,
              pointRadius: 0,
              pointHoverRadius: 5,
              pointHoverBackgroundColor: '#00ffc8',
              fill: true,
              backgroundColor: grad,
              tension: 0.3,
              spanGaps: false,
              order: 3,
            }},
            {{
              label: '摘要记录',
              data: buildDigestDataset(current.labels),
              borderColor: 'transparent',
              backgroundColor: '#ffffff',
              pointBackgroundColor: '#050a14',
              pointBorderColor: '#00ffc8',
              pointBorderWidth: 2,
              pointRadius: 5,
              pointHoverRadius: 7,
              fill: false,
              showLine: false,
              spanGaps: false,
              order: 1,
            }},
            {{
              label: '预测中位数',
              data: fcSeries,
              borderColor: '#ff00b4',
              borderWidth: 2,
              borderDash: [5, 4],
              pointBackgroundColor: '#ff00b4',
              pointBorderColor: '#050a14',
              pointBorderWidth: 2,
              pointRadius: 5,
              pointHoverRadius: 7,
              fill: false,
              tension: 0.2,
              spanGaps: true,
              order: 2,
            }},
          ],
        }},
        options: {{
          responsive: true,
          maintainAspectRatio: false,
          animation: {{ duration: 600, easing: 'easeOutQuart' }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              mode: 'index',
              intersect: false,
              backgroundColor: 'rgba(5,10,20,0.93)',
              borderColor: 'rgba(0,255,200,0.25)',
              borderWidth: 1,
              titleColor: '#00ffc8',
              bodyColor: '#e8f4f8',
              titleFont: {{ family: "'Space Mono', monospace", size: 10 }},
              bodyFont:  {{ family: "'Space Mono', monospace", size: 11 }},
              padding: 10,
              callbacks: {{
                title: items => items[0]?.label || '',
                label: item => {{
                  if (item.parsed.y === null) return null;
                  const labels = ['BTC', '摘要', '预测'];
                  return ` ${{labels[item.datasetIndex]}}: $${{item.parsed.y.toLocaleString()}}`;
                }},
              }},
            }},
          }},
          scales: {{
            x: {{
              grid: {{ color: 'rgba(0,255,200,0.05)', drawBorder: false }},
              ticks: {{
                color: 'rgba(232,244,248,0.4)',
                font: {{ family: "'Space Mono', monospace", size: 10 }},
                maxTicksLimit: 8,
                maxRotation: 0,
              }},
            }},
            y: {{
              min: initRange.min,
              max: initRange.max,
              position: 'right',
              grid: {{ color: 'rgba(0,255,200,0.05)', drawBorder: false }},
              ticks: {{
                color: 'rgba(232,244,248,0.4)',
                font: {{ family: "'Space Mono', monospace", size: 10 }},
                callback: v => '$' + (v / 1000).toFixed(0) + 'K',
                maxTicksLimit: 6,
              }},
            }},
          }},
        }},
      }});

      // ── Time-frame buttons ────────────────────────────────────────────
      document.querySelectorAll('.tf-btn').forEach(btn => {{
        btn.addEventListener('click', () => {{
          document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
          btn.classList.add('active');

          const days = parseInt(btn.dataset.days);
          const sliced = sliceByDays(days);

          // Extend labels with forecast points for the 1W/1M views
          let extLabels = [...sliced.labels];
          let extValues = [...sliced.values];
          if (days <= 30) {{
            fcPoints.forEach(pt => {{
              if (!extLabels.includes(pt.date)) {{
                extLabels.push(pt.date);
                extValues.push(null);
              }}
            }});
          }}

          const newFc      = extLabels.map(lbl => {{ const p = fcPoints.find(x => x.date === lbl); return p ? p.price : null; }});
          const newDigests = buildDigestDataset(extLabels);
          const rng        = yRange([...extValues.filter(Boolean), ...newFc.filter(Boolean)]);

          chart.data.labels                  = extLabels;
          chart.data.datasets[0].data        = extValues;
          chart.data.datasets[1].data        = newDigests;
          chart.data.datasets[2].data        = newFc;
          chart.options.scales.y.min         = rng.min;
          chart.options.scales.y.max         = rng.max;
          chart.update('active');
        }});
      }});
    }})();

    // ── Navigation ────────────────────────────────────────────────────────
    const slides = Array.from(document.querySelectorAll('.slide'));
    const navDots = document.getElementById('nav-dots');
    const progressBar = document.getElementById('progress-bar');

    // Build nav dots
    slides.forEach((slide, i) => {{
      const dot = document.createElement('button');
      dot.className = 'nav-dot';
      dot.setAttribute('aria-label', `幻灯片 ${{i + 1}}`);
      dot.addEventListener('click', () => slide.scrollIntoView({{ behavior: 'smooth' }}));
      navDots.appendChild(dot);
    }});

    const dots = Array.from(navDots.querySelectorAll('.nav-dot'));

    function updateNav() {{
      const scrollTop = document.documentElement.scrollTop || document.body.scrollTop;
      const totalH = document.documentElement.scrollHeight - window.innerHeight;
      const pct = totalH > 0 ? (scrollTop / totalH) * 100 : 0;
      progressBar.style.width = pct + '%';

      const idx = Math.round(scrollTop / window.innerHeight);
      dots.forEach((d, i) => d.classList.toggle('active', i === idx));
    }}

    document.addEventListener('scroll', updateNav, {{ passive: true }});
    updateNav();

    // Keyboard navigation
    document.addEventListener('keydown', e => {{
      const idx = Math.round((document.documentElement.scrollTop || document.body.scrollTop) / window.innerHeight);
      if (e.key === 'ArrowDown' || e.key === ' ') {{
        e.preventDefault();
        if (idx < slides.length - 1) slides[idx + 1].scrollIntoView({{ behavior: 'smooth' }});
      }} else if (e.key === 'ArrowUp') {{
        e.preventDefault();
        if (idx > 0) slides[idx - 1].scrollIntoView({{ behavior: 'smooth' }});
      }}
    }});
  </script>

</body>
</html>"""

    return html


# ── 3. Save and publish ───────────────────────────────────────────────────────

def save_and_publish(html, digests):
    today    = datetime.date.today()
    week_num = today.isocalendar()[1]
    year     = today.year

    # Local archive copy
    local_name = f"bitcoin-weekly-{year}-W{week_num:02d}.html"
    local_path = os.path.join(DIGEST_DIR, local_name)
    with open(local_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✅ Local copy: {local_path}")

    # GitHub Pages copy
    os.makedirs(os.path.dirname(PAGES_FILE), exist_ok=True)
    shutil.copy(local_path, PAGES_FILE)
    print(f"   Pages copy:  {PAGES_FILE}")

    # Git commit + push
    today_str = today.isoformat()
    subprocess.run(["git", "-C", REPO_DIR, "add", "docs/bitcoin-weekly.html"],
                   capture_output=True)
    result = subprocess.run(
        ["git", "-C", REPO_DIR, "commit", "-m", f"Update Bitcoin weekly slides {today_str}"],
        capture_output=True, text=True
    )
    if "nothing to commit" in result.stdout:
        print("   No changes to push — slides unchanged.")
    else:
        push = subprocess.run(
            ["git", "-C", REPO_DIR, "push", "origin", "main"],
            capture_output=True, text=True
        )
        if push.returncode == 0:
            print("   Pushed to GitHub Pages ✅")
        else:
            print(f"   Push failed: {push.stderr.strip()}")

    # Open in browser
    subprocess.run(["open", local_path])
    return local_path


# ── 4. Main ───────────────────────────────────────────────────────────────────

def main():
    print("📂 Loading digest files (last 14 days)...")
    digests = load_week_digests(lookback_days=14)

    if not digests:
        print("❌ No digest files found in the last 14 days.")
        print("   Run /bitcoin first to generate today's digest, then try again.")
        return

    print(f"   Found {len(digests)} digest(s):")
    for d in digests:
        print(f"   • {d['date']}  ${d['actual_price']:,.0f}")

    print("\n🌐 Fetching historical prices from CoinGecko (1Y)...")
    historical = fetch_historical_prices(days=365)
    if historical:
        print(f"   Got {len(historical)} days ({historical[0][0]} → {historical[-1][0]})")
    else:
        print("   ⚠️  No historical data — chart will use digest points only.")

    print("\n🎨 Building weekly slides...")
    html = build_html(digests, historical_prices=historical)

    print("\n💾 Saving and publishing...")
    local_path = save_and_publish(html, digests)

    today   = datetime.date.today()
    week_num = today.isocalendar()[1]
    year     = today.year

    print(f"\n🌐 GitHub Pages URL (once push propagates):")
    print(f"   https://<your-username>.github.io/claude_code_jshao/bitcoin-weekly.html")
    print(f"\n✅ Done! W{week_num} / {year} weekly slides generated.")


if __name__ == "__main__":
    main()
