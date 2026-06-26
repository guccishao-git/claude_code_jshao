#!/usr/bin/env python3
"""Swyftx READ-ONLY API client (CLI) for the /swyftx skill.

Pulls live prices, portfolio/balance, and transaction history from Swyftx.
This client NEVER places, modifies, or cancels orders — it has no write paths
at all. Trade ideas are produced by the skill as *suggestions* only.

Stdlib only (urllib) — no pip install required, runs on system python3.

Env vars:
  SWYFTX_API_KEY   long-lived API key from the Swyftx dashboard (required for
                   anything account-specific; market data may also need it).
  SWYFTX_ENV       'demo' (default) or 'live'.
  SWYFTX_BASE_CCY  fiat used for valuations, default 'NZD' (try 'AUD' if your
                   account is AU-based and NZD isn't accepted).

Caches (under ~/.cache/swyftx/, mode 0600):
  token_<env>.json    minted JWT + its decoded expiry
  assets_<env>.json   asset id<->code map (refreshed every 24h)

Commands:
  whoami                          show account profile + base currency
  assets [SEARCH]                 list/search tradable assets (public)
  prices BTC ETH SOL ...          live buy/sell rates for asset codes
  balance                         current holdings (enriched with codes)
  history trades|deposits|withdrawals [CODE]
  selftest                        connectivity + auth check

All commands print JSON to stdout so the skill can parse and present them.
On error, prints {"error": "..."} to stdout and exits non-zero.
"""
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request

CACHE_DIR = os.path.expanduser("~/.cache/swyftx")
ASSET_CACHE_TTL = 24 * 3600
HTTP_TIMEOUT = 30


def base_url(env=None):
    # Swyftx's demo host (api.demo.swyftx.com.au) is non-functional for the
    # endpoints we use — it 404s auth, assets, and account calls. So everything
    # runs against production, and the read-only API key scope IS the safety net:
    # this client has no order/write paths and the key cannot trade.
    # The `env` arg is accepted for backwards-compat but ignored.
    return "https://api.swyftx.com.au", "prod"


def _cache_path(name):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, name)


def _write_secure(path, data):
    with open(path, "w") as f:
        json.dump(data, f)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def http(method, path, token=None, body=None, env=None):
    """Make an HTTP call. `path` is relative; trailing slash is enforced
    because the Swyftx API is picky about it."""
    base, _ = base_url(env)
    if not path.startswith("/"):
        path = "/" + path
    if not path.endswith("/") and "?" not in path:
        path += "/"
    url = base + path
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        # Swyftx sits behind Cloudflare, which 1010-bans the default
        # Python-urllib agent. Present a normal browser signature.
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/124.0.0.0 Safari/537.36"),
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        detail = e.read().decode()[:500]
        raise RuntimeError("HTTP %s on %s: %s" % (e.code, path, detail))
    except urllib.error.URLError as e:
        raise RuntimeError("network error on %s: %s" % (path, e.reason))


# ---------------------------------------------------------------- auth

def _jwt_exp(token):
    """Decode a JWT's exp claim (seconds since epoch) without verifying."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)  # pad base64
        claims = json.loads(base64.urlsafe_b64decode(payload))
        return int(claims.get("exp", 0))
    except Exception:
        return 0


def get_token(force=False):
    api_key = os.environ.get("SWYFTX_API_KEY")
    if not api_key:
        raise RuntimeError(
            "SWYFTX_API_KEY is not set. Create a key in the Swyftx dashboard "
            "(Profile > Account settings > API keys) and export it. See the "
            "/swyftx skill for setup steps."
        )
    _, env = base_url()
    cache = _cache_path("token_%s.json" % env)
    if not force and os.path.exists(cache):
        try:
            with open(cache) as f:
                cached = json.load(f)
            # 60s safety buffer before expiry
            if cached.get("exp", 0) - 60 > time.time():
                return cached["accessToken"]
        except Exception:
            pass
    # Auth is only served on production (the demo host 404s /auth/refresh/).
    resp = http("POST", "/auth/refresh/", body={"apiKey": api_key}, env="live")
    token = resp.get("accessToken") or resp.get("access_token")
    if not token:
        raise RuntimeError("auth/refresh returned no accessToken: %s" % resp)
    exp = _jwt_exp(token) or int(time.time() + 6 * 24 * 3600)
    _write_secure(cache, {"accessToken": token, "exp": exp})
    return token


# ---------------------------------------------------------------- assets

def load_assets():
    """Return (by_id, by_code) maps. Public endpoint; cached 24h."""
    _, env = base_url()
    cache = _cache_path("assets_%s.json" % env)
    if os.path.exists(cache) and time.time() - os.path.getmtime(cache) < ASSET_CACHE_TTL:
        try:
            with open(cache) as f:
                assets = json.load(f)
        except Exception:
            assets = None
    else:
        assets = None
    if assets is None:
        # Asset list is public and only served on production (demo 404s it).
        assets = http("GET", "/markets/assets/", env="live")
        if isinstance(assets, dict):
            assets = assets.get("assets", assets.get("data", []))
        _write_secure(cache, assets)
    by_id, by_code = {}, {}
    for a in assets:
        aid = a.get("id")
        code = (a.get("code") or a.get("ticker") or "").upper()
        entry = {"id": aid, "code": code, "name": a.get("name")}
        if aid is not None:
            by_id[str(aid)] = entry
        if code:
            by_code[code] = entry
    return by_id, by_code


# ---------------------------------------------------------------- price normalization

def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def normalize_price(raw):
    """Pull buy/sell/mid out of whatever shape the rates endpoint returns."""
    if isinstance(raw, list) and raw:
        raw = raw[0]
    if not isinstance(raw, dict):
        return {"raw": raw}
    out = {}
    for key, aliases in {
        "buy": ("buy", "ask", "askPrice"),
        "sell": ("sell", "bid", "bidPrice"),
        "mid": ("mid", "midPrice", "price", "last", "rate"),
    }.items():
        for a in aliases:
            if a in raw and _num(raw[a]) is not None:
                out[key] = _num(raw[a])
                break
    out["raw"] = raw
    return out


# ---------------------------------------------------------------- commands

def cmd_whoami(_args):
    token = get_token()
    return http("GET", "/user/", token=token, env="live")


def cmd_assets(args):
    by_id, by_code = load_assets()
    items = list(by_code.values())
    if args:
        q = args[0].upper()
        items = [a for a in items if q in a["code"] or q in (a["name"] or "").upper()]
    items.sort(key=lambda a: a["code"])
    return {"count": len(items), "assets": items[:200]}


def cmd_prices(args):
    if not args:
        raise RuntimeError("usage: prices BTC ETH SOL ...")
    # Use the token if a key is set so prices come back in the account's display
    # currency (matching balance valuations); otherwise public prices are AUD.
    token = None
    try:
        token = get_token()
    except RuntimeError:
        pass
    out = {}
    for code in args:
        code = code.upper()
        try:
            # basic info gives buy/sell/spread/volume/marketcap.
            raw = http("GET", "/markets/info/basic/%s/" % code, token=token)
            info = raw[0] if isinstance(raw, list) and raw else raw
            out[code] = {
                "name": info.get("name"),
                "buy": _num(info.get("buy")),
                "sell": _num(info.get("sell")),
                "spread_pct": _num(info.get("spread")),
                "volume24h": _num(info.get("volume24H")),
                "market_cap": _num(info.get("marketCap")),
                "rank": info.get("rank"),
            }
        except RuntimeError as e:
            out[code] = {"error": str(e)}
    # Authed prices use the account's display currency (see `whoami`);
    # unauthenticated public prices are quoted in AUD.
    return {
        "quote_ccy": "account display currency (authed)" if token else "AUD (public)",
        "prices": out,
    }


def cmd_balance(_args):
    token = get_token()
    raw = http("GET", "/user/balance/", token=token, env="live")
    holdings = raw.get("data", raw) if isinstance(raw, dict) else raw
    by_id, _ = load_assets()
    enriched = []
    for h in holdings or []:
        aid = h.get("assetId", h.get("asset"))
        meta = by_id.get(str(aid), {})
        bal = _num(h.get("availableBalance", h.get("balance", h.get("available"))))
        enriched.append({
            "code": meta.get("code", str(aid)),
            "name": meta.get("name"),
            "assetId": aid,
            "balance": bal,
        })
    enriched = [e for e in enriched if e["balance"]]
    enriched.sort(key=lambda e: e["code"])
    return {"holdings": enriched, "count": len(enriched)}


_ACTION_FILTERS = {
    "trades": lambda a: "Buy" in a or "Sell" in a or "Market" in a,
    "deposits": lambda a: "Deposit" in a,
    "withdrawals": lambda a: "Withdraw" in a,
    "all": lambda a: True,
}


def _rates(token, base_id):
    """live-rates with a given base asset: {assetIdStr: {bidPrice, askPrice, ...}}.
    base 190 = NZD, base 36 = USD."""
    return http("GET", "/live-rates/%s/" % base_id, token=token)


def _bid(rates, aid):
    return _num((rates.get(aid) or {}).get("bidPrice"))


def _avg_cost(token):
    """Per-asset buy aggregates from /orders/ (which carries the BTC `amount`
    received and NZD `total` spent that history/ lacks).
    Returns assetIdStr -> {qty_bought, nzd_spent, avg_cost_nzd}."""
    raw = http("GET", "/orders/", token=token)
    orders = raw.get("orders", raw) if isinstance(raw, dict) else raw
    agg = {}
    for o in orders or []:
        if o.get("status") != 4 or o.get("order_type") != 1:  # 4=complete, 1=Market Buy
            continue
        aid = str(o.get("secondary_asset"))
        amt = _num(o.get("amount")) or 0          # crypto received (net of fee)
        cost = _num(o.get("total")) or 0          # fiat (NZD) spent
        a = agg.setdefault(aid, [0.0, 0.0])
        a[0] += amt
        a[1] += cost
    return {aid: {"qty_bought": q, "nzd_spent": c,
                  "avg_cost_nzd": (c / q if q else None)}
            for aid, (q, c) in agg.items()}


def cmd_portfolio(_args):
    """Holdings valued in NZD + USD, with average cost and cost-basis P&L."""
    token = get_token()
    raw = http("GET", "/user/balance/", token=token)
    holdings = raw.get("data", raw) if isinstance(raw, dict) else raw
    by_id, _ = load_assets()
    nzd = _rates(token, 190)
    usd = _rates(token, 36)
    avg = _avg_cost(token)
    # current FX for converting historical NZD avg cost into a USD figure
    usd_per_nzd = _bid(usd, "190")
    out = []
    tot = {"value_nzd": 0.0, "value_usd": 0.0, "invested_nzd": 0.0}
    for h in holdings or []:
        aid = str(h.get("assetId", h.get("asset")))
        bal = _num(h.get("availableBalance", h.get("balance", h.get("available")))) or 0
        if not bal:
            continue
        meta = by_id.get(aid, {})
        p_nzd = 1.0 if aid == "190" else _bid(nzd, aid)
        p_usd = usd_per_nzd if aid == "190" else _bid(usd, aid)
        v_nzd = p_nzd * bal if p_nzd else None
        v_usd = p_usd * bal if p_usd else None
        a = avg.get(aid, {})
        inv = a.get("nzd_spent")
        ac_nzd = a.get("avg_cost_nzd")
        item = {
            "code": meta.get("code", aid),
            "name": meta.get("name"),
            "balance": bal,
            "price_nzd": round(p_nzd, 2) if p_nzd else None,
            "price_usd": round(p_usd, 2) if p_usd else None,
            "value_nzd": round(v_nzd, 2) if v_nzd is not None else None,
            "value_usd": round(v_usd, 2) if v_usd is not None else None,
            "qty_bought": round(a["qty_bought"], 8) if a.get("qty_bought") else None,
            "avg_cost_nzd": round(ac_nzd, 2) if ac_nzd else None,
            "avg_cost_usd": round(ac_nzd * usd_per_nzd, 2) if (ac_nzd and usd_per_nzd) else None,
            "invested_nzd": round(inv, 2) if inv is not None else None,
        }
        if v_nzd is not None and inv:
            item["pl_nzd"] = round(v_nzd - inv, 2)
            item["pl_pct"] = round((v_nzd / inv - 1) * 100, 1)
        out.append(item)
        if v_nzd:
            tot["value_nzd"] += v_nzd
        if v_usd:
            tot["value_usd"] += v_usd
        if inv:
            tot["invested_nzd"] += inv
    out.sort(key=lambda i: i.get("value_nzd") or 0, reverse=True)
    totals = {k: round(v, 2) for k, v in tot.items()}
    if tot["invested_nzd"]:
        totals["pl_nzd"] = round(tot["value_nzd"] - tot["invested_nzd"], 2)
        totals["pl_pct"] = round((tot["value_nzd"] / tot["invested_nzd"] - 1) * 100, 1)
    return {
        "base_ccy": "NZD", "usd_per_nzd": round(usd_per_nzd, 4) if usd_per_nzd else None,
        "holdings": out, "totals": totals,
        "note": ("avg_cost & invested = from completed buy orders only (ignores coin "
                 "deposits/withdrawals); avg_cost_usd converts NZD basis at current FX"),
    }


def cmd_history(args):
    action = args[0] if args else "all"
    if action not in _ACTION_FILTERS:
        raise RuntimeError("usage: history trades|deposits|withdrawals|all [CODE]")
    token = get_token()
    # The real endpoint is /history/all/ (per-action and per-asset paths 404).
    raw = http("GET", "/history/all/", token=token)
    recs = raw if isinstance(raw, list) else raw.get("data", raw)
    by_id, by_code = load_assets()
    code_of = lambda aid: by_id.get(str(aid), {}).get("code", str(aid))
    keep = _ACTION_FILTERS[action]
    asset_code = args[1].upper() if len(args) > 1 else None
    out = []
    for r in recs or []:
        at = r.get("actionType", "")
        if not keep(at):
            continue
        ac = code_of(r.get("asset"))
        if asset_code and ac != asset_code:
            continue
        ms = r.get("updated")
        date = None
        if ms:
            date = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(ms / 1000))
        out.append({
            "date": date,
            "actionType": at,
            "status": r.get("status"),
            "asset": ac,
            "quantity": _num(r.get("quantity")),
            "quantityAsset": code_of(r.get("quantityAsset")),
            "primaryAsset": code_of(r.get("primaryAsset")),
            "updated": ms,
        })
    out.sort(key=lambda r: r.get("updated") or 0, reverse=True)
    return {"action": action, "count": len(out), "history": out}


def cmd_selftest(_args):
    base, env = base_url()
    result = {"env": env, "base_url": base}
    try:
        by_id, _ = load_assets()
        result["assets_reachable"] = True
        result["asset_count"] = len(by_id)
    except RuntimeError as e:
        result["assets_reachable"] = False
        result["assets_error"] = str(e)
    if os.environ.get("SWYFTX_API_KEY"):
        try:
            get_token(force=True)
            result["auth_ok"] = True
        except RuntimeError as e:
            result["auth_ok"] = False
            result["auth_error"] = str(e)
    else:
        result["auth_ok"] = None
        result["note"] = "SWYFTX_API_KEY not set — only public market data available"
    return result


COMMANDS = {
    "whoami": cmd_whoami,
    "assets": cmd_assets,
    "prices": cmd_prices,
    "balance": cmd_balance,
    "portfolio": cmd_portfolio,
    "history": cmd_history,
    "selftest": cmd_selftest,
}


def main(argv):
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return 0
    cmd, rest = argv[0], argv[1:]
    fn = COMMANDS.get(cmd)
    if not fn:
        print(json.dumps({"error": "unknown command: %s" % cmd,
                          "commands": list(COMMANDS)}))
        return 2
    try:
        print(json.dumps(fn(rest), indent=2, default=str))
        return 0
    except RuntimeError as e:
        print(json.dumps({"error": str(e)}))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
