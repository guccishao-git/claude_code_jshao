---
name: swyftx
description: Connect to the Swyftx crypto exchange (AU/NZ) for live prices, portfolio/balance, transaction history, and read-only trade *suggestions*. Trigger whenever the user asks about Swyftx, their crypto holdings/portfolio on Swyftx, Swyftx prices, "how's my crypto doing", "should I buy/sell X", or wants a Swyftx market check. READ-ONLY — never places, modifies, or cancels orders.
---

# Swyftx Skill (read-only + trade suggestions)

Connect to **Swyftx** (Australian/NZ crypto exchange) to pull **live prices**,
**portfolio/balance**, and **transaction history**, and to produce **trade
suggestions** — analysis only.

> ⛔ **HARD RULE: this skill NEVER trades.** It does not place, modify, or cancel
> orders, and the backing client has no write/order code paths at all. Any buy/sell
> idea is a **suggestion** for the user to act on themselves in the Swyftx app.
> If the user asks you to actually execute a trade, decline and point them to the app.

Backed by `scripts/swyftx/swyftx_client.py` (stdlib only — no pip install).

## Environment — production read-only only

There is **no working sandbox.** Swyftx's demo host (`api.demo.swyftx.com.au`) 404s on
auth, `/markets/assets/`, and account calls, so **everything runs against production**
(`api.swyftx.com.au`). Safety comes from the **key being read-only** and this client
having **zero order/write code paths** — it physically cannot trade. `SWYFTX_ENV` is
ignored. (See [[project_swyftx_skill]].)

## API key setup

If the user hasn't created a key, walk them through it:

1. Log in at **swyftx.com** → **Profile → Account settings → API Keys → Create a key**.
   - Assign **read-only scope only** (account/funds/orders/balance/tax read). **Never**
     grant trade/write scope — this skill never trades and shouldn't be able to.
2. Copy the key (shown once) and add it to **`~/.zshrc`** (already done for this user):
   ```bash
   export SWYFTX_API_KEY="paste-key-here"
   ```
   ⚠️ Never print, log, or commit the key. It is read only from the environment.

### ⚠️ Running commands — interactive shell required

The key lives in `~/.zshrc`, which only **interactive** shells source. The Bash tool's
default non-interactive shell will NOT see it, so **wrap every account command in
`zsh -i -c '...'`**. (Alternatively the user can move the export to `~/.zshenv`.)

## How to run

```bash
cd /Users/jason.shao/Documents/GitHub1/claude_code_jshao

# Public market data — no key needed, plain shell is fine:
python3 scripts/swyftx/swyftx_client.py prices BTC ETH SOL
python3 scripts/swyftx/swyftx_client.py assets eth

# Account data — needs the key from ~/.zshrc, so use an interactive shell:
zsh -i -c 'python3 scripts/swyftx/swyftx_client.py whoami'              # profile
zsh -i -c 'python3 scripts/swyftx/swyftx_client.py balance'            # holdings
zsh -i -c 'python3 scripts/swyftx/swyftx_client.py portfolio'         # holdings + NZD value + P&L (one call)
zsh -i -c 'python3 scripts/swyftx/swyftx_client.py history trades BTC' # trades|deposits|withdrawals|all, asset optional
zsh -i -c 'python3 scripts/swyftx/swyftx_client.py selftest'          # connectivity + auth
```

### Export transaction history to xlsx

`swyftx_export.py` writes a styled 2-sheet workbook (Portfolio summary + Transactions)
to `~/Documents/Swyftx/swyftx-transactions-YYYY-MM-DD.xlsx`. It needs **openpyxl**, which
lives in the repo venv — so run it with the **venv python** (the interactive shell's
`python3` is Homebrew and lacks openpyxl):

```bash
VENV=/Users/jason.shao/Documents/GitHub1/claude_code_jshao/.venv/bin/python3
zsh -i -c "$VENV scripts/swyftx/swyftx_export.py"        # default dated path
zsh -i -c "$VENV scripts/swyftx/swyftx_export.py /path/to/out.xlsx"
```

Every command prints JSON to stdout. Parse it and present results cleanly — **do not dump
raw JSON at the user**, and never echo sensitive profile fields (Intercom JWTs, verification
IDs, `user_hash`, full address/phone). On `{"error": ...}`, read the message and help fix it
(usually a missing/expired key — refresh is automatic — or the key not being visible to a
non-interactive shell).

## Workflow

1. **Figure out intent** — price check, portfolio view, history, or a buy/sell opinion.
   Default environment is **demo** unless the user says "live"/"real account".

2. **Run the relevant command(s)** and parse the JSON.

3. **Present results scannably** (data-engineer tone, casual):
   - **Prices:** show buy/sell, 24h context, spread. Note `quote_ccy` (AUD for
     unauthenticated public prices; account base currency when authed).
   - **Portfolio:** table of holdings (code, balance). If you have live prices, multiply to
     estimate value per holding and a total in the base currency — label it an estimate.
   - **History:** summarize counts and notable transactions; offer to export to CSV/xlsx
     (use the `xlsx` skill) if they want a record.

4. **Trade suggestions (analysis only):** when asked "should I buy/sell X" or for ideas:
   - Pull live prices (and the user's holdings if relevant). Optionally use **web search**
     for recent market context/news.
   - Give a clear, reasoned **suggestion** with the *why* (price action, spread, their
     position size, concentration risk), and always state it's **not financial advice**
     and the skill won't execute it.
   - Keep it honest about uncertainty — no fake precision.

## Gotchas

- **Asset IDs vs codes:** some endpoints want a numeric id, others the code (BTC). The
  client resolves this via the cached `/markets/assets/` map automatically.
- **Token lifetime ~1 week:** the client mints a JWT from the API key and caches it
  (`~/.cache/swyftx/token_prod.json`, mode 0600), refreshing automatically on expiry.
- **Cloudflare:** Swyftx 1010-bans default user agents; the client sends a browser UA.
- **Pricing currency (subtle!):** authed `prices`/valuations come back in the account's
  **primary/country currency = `countryCurrency.code` (NZD here)**, NOT the display
  `currency.code` (which reads USD but is not what the price endpoints return). Public
  no-key prices are **AUD**. To value a holding in NZD precisely, use
  `/live-rates/190/` (base 190 = NZD) and read the asset's `bidPrice`/`midPrice`.
  Always label the currency, and don't trust the USD display field for valuations.
