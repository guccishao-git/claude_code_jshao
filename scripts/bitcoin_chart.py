"""
Bitcoin Forecast vs. Actual Price Chart
Reads digest files from ~/Documents/BitCoinNewsDaily/,
fetches real historical prices from CoinGecko,
and generates an interactive HTML chart.
"""

import os
import re
import json
import datetime
import requests
import glob

import plotly.graph_objects as go

DIGEST_DIR = os.path.expanduser("~/Documents/BitCoinNewsDaily")
OUTPUT_FILE = os.path.join(DIGEST_DIR, "bitcoin-forecast-chart.html")


# ── 1. Parse digest files ─────────────────────────────────────────────────────

def parse_digest(filepath):
    """
    Extract date, actual price, and forecast ranges from a digest file.
    Works with both English and Chinese digest formats.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # ── Date from filename ────────────────────────────────────────────────
    fname = os.path.basename(filepath)
    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", fname)
    if not date_match:
        return None
    date = datetime.date.fromisoformat(date_match.group(1))

    # ── Actual price ──────────────────────────────────────────────────────
    # Look specifically inside the price table row to avoid catching prices
    # mentioned in the summary text (e.g. "从高点约 $97,000 已跌去…")
    actual_price = None

    # Chinese format: | **价格（USD）** | $67,811 |
    m = re.search(r"\|\s*\*\*价格[（(]USD[）)]\*\*\s*\|\s*\*?\*?\$\s*([\d,]+)", content)
    if m:
        actual_price = float(m.group(1).replace(",", ""))

    # English format: | Price (USD) | **$67,341** |
    if actual_price is None:
        m = re.search(r"\|\s*\*?\*?Price[^|]*\|\s*\*?\*?\$\s*([\d,]+)", content)
        if m:
            actual_price = float(m.group(1).replace(",", ""))

    # Chinese fallback: **约 $67,243 美元**  (used in older digest format)
    if actual_price is None:
        m = re.search(r"\*\*(?:约\s*)?\$\s*([\d,]+)\s*美元\*\*", content)
        if m:
            actual_price = float(m.group(1).replace(",", ""))

    # Last-resort fallback: first table row with a 5+ digit dollar figure
    if actual_price is None:
        for line in content.splitlines():
            if "|" in line:
                m = re.search(r"\|\s*\*?\*?\$\s*([\d,]{5,})\s*\*?\*?\s*\|", line)
                if m:
                    actual_price = float(m.group(1).replace(",", ""))
                    break

    # ── Forecasts ─────────────────────────────────────────────────────────
    # Find rows from the forecast table
    # Handles both English ("1 Week", "1 Month") and Chinese ("1周", "1个月")

    forecasts = {}

    def parse_forecast_line(pattern):
        """
        Parse a forecast line supporting two formats:
          1. Target ± margin:  $69,500 ± $1,500  →  (68000, 71000)
          2. Range:            $65,000–$73,300    →  (65000, 73300)
        Returns (low, high) or None.
        """
        m = re.search(pattern, content, re.IGNORECASE)
        if not m:
            return None
        line = m.group(0)
        # Format 1: target ± margin
        pm = re.search(r"\$([\d,]+)\s*[±\+\-]\s*\$?([\d,]+)", line)
        if pm:
            target = float(pm.group(1).replace(",", ""))
            margin = float(pm.group(2).replace(",", ""))
            return target - margin, target + margin
        # Format 2: low–high range
        rng = re.search(r"\$([\d,]+)[^\d$]+\$([\d,]+)", line)
        if rng:
            return float(rng.group(1).replace(",", "")), float(rng.group(2).replace(",", ""))
        # Format 3: single value fallback (±0.5%)
        sv = re.search(r"\$([\d,]+)", line)
        if sv:
            v = float(sv.group(1).replace(",", ""))
            return v * 0.995, v * 1.005
        return None

    # 1-week
    result = parse_forecast_line(r"(?:1\s*Week|下周|1周)[^\n]+")
    if result:
        forecasts["1w_low"], forecasts["1w_high"] = result

    # 1-month
    result = parse_forecast_line(r"(?:1\s*Month|1个月[（\(]?基准[）\)]?|1个月)[^\n]+")
    if result:
        forecasts["1m_low"], forecasts["1m_high"] = result

    # 1-year (end of year) — consensus range
    # Handles "$143,000", "$143K", "143,000" etc.
    def parse_price_token(s):
        s = s.replace(",", "").strip()
        if s.endswith("K") or s.endswith("k"):
            return float(s[:-1]) * 1000
        return float(s)

    year_match = re.search(
        r"(?:1\s*Year|年底\d{4}[（\(]?主流|年底\d{4})[^\n]*?\$([\d,K]+)[^\n–-]*?[\-–]\s*\$([\d,K]+)",
        content, re.IGNORECASE
    )
    if year_match:
        forecasts["1y_low"] = parse_price_token(year_match.group(1))
        forecasts["1y_high"] = parse_price_token(year_match.group(2))

    return {
        "date": date,
        "actual_price": actual_price,
        "forecasts": forecasts,
        "file": fname,
    }


def load_digests():
    files = sorted(glob.glob(os.path.join(DIGEST_DIR, "digest-*.md")))
    results = []
    for f in files:
        parsed = parse_digest(f)
        if parsed and parsed["actual_price"]:
            results.append(parsed)
    return results


# ── 2. Fetch real BTC prices from CoinGecko ───────────────────────────────────

def fetch_real_prices(days=90):
    url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
    params = {"vs_currency": "usd", "days": days, "interval": "daily"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        prices = data.get("prices", [])
        result = []
        for ts_ms, price in prices:
            dt = datetime.datetime.utcfromtimestamp(ts_ms / 1000).date()
            result.append((dt, price))
        return result
    except Exception as e:
        print(f"Warning: Could not fetch CoinGecko data — {e}")
        return []


# ── 3. Build Plotly chart ─────────────────────────────────────────────────────

# Color palette — clean financial style
C_PRICE      = "#E8640C"              # deep bitcoin orange
C_PRICE_FILL = "rgba(232,100,12,0.08)"  # faint fill under price line
C_1W_RGB     = "59,130,246"           # blue (used in rgba strings)
C_1M_RGB     = "16,185,129"           # green
C_YE_line    = "#D97706"              # amber for year-end
C_GRID       = "rgba(203,213,225,0.6)"
C_AXIS       = "#94a3b8"


def _hl_annotations(dates, prices, window_start, base_anns):
    """Return base_anns + high/low annotations for prices within window_start..today."""
    pairs = [(d, p) for d, p in zip(dates, prices) if d >= window_start]
    if not pairs:
        return list(base_anns)
    w_dates, w_prices = zip(*pairs)
    hi_i = w_prices.index(max(w_prices))
    lo_i = w_prices.index(min(w_prices))
    return list(base_anns) + [
        dict(
            x=str(w_dates[hi_i]), y=w_prices[hi_i],
            text=f"<b>High: ${w_prices[hi_i]:,.0f}</b>",
            xanchor="center", yanchor="bottom",
            showarrow=True, arrowhead=2, arrowcolor="#16a34a", arrowsize=0.8,
            ax=0, ay=-36,
            font=dict(size=11, color="#16a34a"),
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="#16a34a", borderwidth=1, borderpad=4,
        ),
        dict(
            x=str(w_dates[lo_i]), y=w_prices[lo_i],
            text=f"<b>Low: ${w_prices[lo_i]:,.0f}</b>",
            xanchor="center", yanchor="top",
            showarrow=True, arrowhead=2, arrowcolor="#dc2626", arrowsize=0.8,
            ax=0, ay=36,
            font=dict(size=11, color="#dc2626"),
            bgcolor="rgba(255,255,255,0.88)",
            bordercolor="#dc2626", borderwidth=1, borderpad=4,
        ),
    ]


def build_chart(digests, real_prices):
    fig = go.Figure()

    # ── Forecast bands (drawn first, behind everything) ───────────────────
    first_1w = True
    first_1m = True

    for d in digests:
        digest_date = d["date"]
        fc = d["forecasts"]

        if "1w_low" in fc and "1w_high" in fc:
            end_1w = digest_date + datetime.timedelta(days=7)
            _add_band(fig, digest_date, end_1w, fc["1w_low"], fc["1w_high"],
                      base_rgb=C_1W_RGB,
                      legend_name="1-Week Forecast Range",
                      show_legend=first_1w, legend_group="1w",
                      hover_date=digest_date)
            first_1w = False

        if "1m_low" in fc and "1m_high" in fc:
            end_1m = digest_date + datetime.timedelta(days=30)
            _add_band(fig, digest_date, end_1m, fc["1m_low"], fc["1m_high"],
                      base_rgb=C_1M_RGB,
                      legend_name="1-Month Forecast Range",
                      show_legend=first_1m, legend_group="1m",
                      hover_date=digest_date)
            first_1m = False

    # ── Year-end target lines ─────────────────────────────────────────────
    ye_anns = []
    ye_digest = next((d for d in reversed(digests) if "1y_low" in d["forecasts"]), None)
    if ye_digest:
        fc = ye_digest["forecasts"]
        x0 = ye_digest["date"]
        x1 = datetime.date(x0.year, 12, 31)
        for level, label in [
            (fc["1y_low"],  f"Year-End Low · ${fc['1y_low']/1000:.0f}K"),
            (fc["1y_high"], f"Year-End High · ${fc['1y_high']/1000:.0f}K"),
        ]:
            fig.add_shape(type="line", x0=x0, x1=x1, y0=level, y1=level,
                          line=dict(color=C_YE_line, width=1.5, dash="dot"))
            ye_anns.append(dict(
                x=str(x1), y=level, text=f"<b>{label}</b>",
                xanchor="right", yanchor="bottom", showarrow=False,
                font=dict(size=10, color=C_YE_line),
                bgcolor="rgba(255,255,255,0.8)", borderpad=4,
            ))
        fig.add_trace(go.Scatter(
            x=[None], y=[None], mode="lines",
            line=dict(color=C_YE_line, width=1.5, dash="dot"),
            name=f"Year-End Target ({x0.year})", showlegend=True,
        ))

    # ── Actual price line ─────────────────────────────────────────────────
    if real_prices:
        dates_real  = [r[0] for r in real_prices]
        prices_real = [r[1] for r in real_prices]

        # Baseline trace at the minimum price (creates a tight fill band)
        price_min = min(prices_real) * 0.995
        fig.add_trace(go.Scatter(
            x=dates_real, y=[price_min] * len(dates_real),
            mode="lines", line=dict(width=0),
            showlegend=False, hoverinfo="skip",
        ))

        # Price line with fill down to the baseline
        fig.add_trace(go.Scatter(
            x=dates_real, y=prices_real,
            mode="lines", name="BTC Actual Price",
            line=dict(color=C_PRICE, width=2.5),
            fill="tonexty", fillcolor=C_PRICE_FILL,
            hovertemplate="<b>%{x|%b %d, %Y}</b><br>Price: <b>$%{y:,.0f}</b><extra></extra>",
        ))

        # Latest price label — stored for reuse in all annotation sets
        latest_date  = dates_real[-1]
        latest_price = prices_real[-1]
        latest_ann = dict(
            x=str(latest_date), y=latest_price,
            text=f"<b>${latest_price:,.0f}</b>",
            xanchor="left", yanchor="middle",
            showarrow=False,
            font=dict(size=12, color=C_PRICE),
            bgcolor="rgba(255,255,255,0.85)",
            borderpad=4, xshift=8,
        )

    # ── Digest price markers ──────────────────────────────────────────────
    marker_dates  = [d["date"]         for d in digests]
    marker_prices = [d["actual_price"] for d in digests]
    fig.add_trace(go.Scatter(
        x=marker_dates, y=marker_prices,
        mode="markers", name="Recorded Price (digest)",
        marker=dict(size=8, color="white", symbol="circle",
                    line=dict(color=C_PRICE, width=2.5)),
        hovertemplate="<b>%{x|%b %d, %Y}</b><br>Recorded: <b>$%{y:,.0f}</b><extra></extra>",
    ))

    # ── Compute sensible default view window ─────────────────────────────
    today = datetime.date.today()
    x_start = today - datetime.timedelta(days=90)
    x_end   = today + datetime.timedelta(days=35)   # show 5 weeks of forecasts

    # Y range: fit to visible prices + near-term forecasts only
    visible_prices = [p for d, p in real_prices] if real_prices else []
    near_fc_prices = []
    for d in digests:
        fc = d["forecasts"]
        near_fc_prices += [v for k, v in fc.items() if k in ("1w_low","1w_high","1m_low","1m_high")]
    all_visible = visible_prices + near_fc_prices
    y_min = min(all_visible) * 0.94 if all_visible else 0
    y_max = max(all_visible) * 1.06 if all_visible else 200000

    # ── Layout ────────────────────────────────────────────────────────────
    fig.update_layout(
        title=dict(
            text=(
                "<b>Bitcoin · Actual Price vs Forecast Ranges</b>"
                f"<br><sup style='color:#64748b'>Updated {today.strftime('%B %d, %Y')}</sup>"
            ),
            font=dict(size=20, color="#0f172a", family="Georgia, serif"),
            x=0.0, xanchor="left", pad=dict(l=10),
        ),
        xaxis=dict(
            showgrid=True, gridcolor=C_GRID, gridwidth=1,
            linecolor=C_AXIS, tickcolor=C_AXIS, tickfont=dict(color="#475569"),
            title=None,
            range=[x_start.isoformat(), x_end.isoformat()],
            rangeslider=dict(visible=True, thickness=0.05, bgcolor="#f8fafc"),
        ),
        yaxis=dict(
            showgrid=True, gridcolor=C_GRID, gridwidth=1,
            linecolor=C_AXIS, tickcolor=C_AXIS, tickfont=dict(color="#475569"),
            tickformat="$,.0f", title=None,
            side="right",
            range=[y_min, y_max],
        ),
        updatemenus=[dict(
            type="buttons",
            direction="right",
            x=0, xanchor="left",
            y=1.12, yanchor="top",
            bgcolor="#f1f5f9",
            bordercolor=C_GRID, borderwidth=1,
            font=dict(size=11, color="#334155"),
            buttons=[
                dict(label="1W", method="relayout", args=[{
                    "xaxis.range": [
                        (today - datetime.timedelta(days=7)).isoformat(),
                        (today + datetime.timedelta(days=3)).isoformat(),
                    ],
                    "annotations": _hl_annotations(
                        dates_real, prices_real,
                        today - datetime.timedelta(days=7),
                        [latest_ann] + ye_anns
                    ),
                }]),
                dict(label="1M", method="relayout", args=[{
                    "xaxis.range": [
                        (today - datetime.timedelta(days=30)).isoformat(),
                        (today + datetime.timedelta(days=7)).isoformat(),
                    ],
                    "annotations": _hl_annotations(
                        dates_real, prices_real,
                        today - datetime.timedelta(days=30),
                        [latest_ann] + ye_anns
                    ),
                }]),
                dict(label="3M", method="relayout", args=[{
                    "xaxis.range": [
                        (today - datetime.timedelta(days=90)).isoformat(),
                        (today + datetime.timedelta(days=14)).isoformat(),
                    ],
                    "annotations": _hl_annotations(
                        dates_real, prices_real,
                        today - datetime.timedelta(days=90),
                        [latest_ann] + ye_anns
                    ),
                }]),
                dict(label="All", method="relayout", args=[{
                    "xaxis.autorange": True,
                    "annotations": _hl_annotations(
                        dates_real, prices_real,
                        dates_real[0],
                        [latest_ann] + ye_anns
                    ),
                }]),
            ],
        )],
        dragmode="pan",
        hovermode="x unified",
        hoverlabel=dict(
            bgcolor="white", bordercolor=C_GRID,
            font=dict(size=12, color="#0f172a"),
        ),
        legend=dict(
            orientation="v",
            x=0.01, y=0.99,
            xanchor="left", yanchor="top",
            bgcolor="rgba(255,255,255,0.92)",
            bordercolor="#cbd5e1", borderwidth=1,
            font=dict(size=13, color="#1e293b"),
            itemsizing="constant",
            itemwidth=40,
        ),
        plot_bgcolor="white",
        paper_bgcolor="white",
        font=dict(family="Inter, Arial, sans-serif", color="#334155"),
        margin=dict(t=80, b=60, l=20, r=80),
        height=580,
    )

    # ── Default annotations (3M view = default window) ───────────────────
    if real_prices:
        default_anns = _hl_annotations(
            dates_real, prices_real,
            today - datetime.timedelta(days=90),
            [latest_ann] + ye_anns
        )
        fig.update_layout(annotations=default_anns)

    # Subtle top border line
    fig.add_shape(type="line", xref="paper", yref="paper",
                  x0=0, x1=1, y0=1, y1=1,
                  line=dict(color=C_PRICE, width=3))

    return fig


def _add_band(fig, x0, x1, low, high, base_rgb,
              legend_name, show_legend, legend_group, hover_date):
    """
    Fading gradient forecast band.
    Solid at x0, fades to transparent at x1 using N vertical slices.
    """
    N = 12
    total_days = max((x1 - x0).days, 1)
    slice_days = total_days / N

    for i in range(N):
        # Opacity curve: starts at 0.30, fades with a smooth curve
        alpha = 0.30 * ((N - i) / N) ** 1.8
        slice_x0 = x0 + datetime.timedelta(days=i * slice_days)
        slice_x1 = x0 + datetime.timedelta(days=(i + 1) * slice_days)

        fig.add_trace(go.Scatter(
            x=[slice_x0, slice_x1, slice_x1, slice_x0, slice_x0],
            y=[low, low, high, high, low],
            fill="toself",
            fillcolor=f"rgba({base_rgb},{alpha:.3f})",
            line=dict(width=0),
            mode="lines",
            legendgroup=legend_group,
            showlegend=(show_legend and i == 0),
            name=legend_name,
            hoverinfo="skip",
        ))

    # Solid left edge line
    edge_color = f"rgba({base_rgb},0.7)"
    fig.add_shape(type="line", x0=x0, x1=x0, y0=low, y1=high,
                  line=dict(color=edge_color, width=2))

    # Invisible hover trace over full band
    fig.add_trace(go.Scatter(
        x=[x0, x1, x1, x0, x0],
        y=[low, low, high, high, low],
        fill="toself", fillcolor="rgba(0,0,0,0)",
        line=dict(width=0), mode="lines",
        legendgroup=legend_group, showlegend=False,
        hovertemplate=(
            f"<b>{legend_name}</b><br>"
            f"From: {hover_date}<br>"
            f"$%{{y:,.0f}}<extra></extra>"
        ),
    ))


# ── 4. Main ───────────────────────────────────────────────────────────────────

def main():
    print("📂 Reading digest files...")
    digests = load_digests()
    if not digests:
        print("❌ No digest files found. Run /bitcoin first to generate them.")
        return

    print(f"   Found {len(digests)} digest(s):")
    for d in digests:
        print(f"   • {d['date']}  price: ${d['actual_price']:,.0f}  forecasts: {d['forecasts']}")

    print("\n🌐 Fetching historical prices from CoinGecko...")
    real_prices = fetch_real_prices(days=90)
    if real_prices:
        print(f"   Got {len(real_prices)} days of data ({real_prices[0][0]} → {real_prices[-1][0]})")
    else:
        print("   ⚠️  Could not fetch live data — showing digest price points only.")

    print("\n📊 Building chart...")
    fig = build_chart(digests, real_prices)
    fig.write_html(OUTPUT_FILE, include_plotlyjs="cdn")
    print(f"\n✅ Chart saved to: {OUTPUT_FILE}")
    print("   Opening in browser...")

    # Auto-open in default browser
    import subprocess
    subprocess.run(["open", OUTPUT_FILE])


if __name__ == "__main__":
    main()
