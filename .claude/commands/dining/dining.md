---
name: dining
description: Help the user find a restaurant and reserve a table in New Zealand (default Auckland), across the platforms that actually dominate here — SevenRooms, ResDiary, First Table, Now Book It. Trigger whenever the user wants to book/reserve a table, find somewhere to eat out, or says "订餐厅 / 订位 / 帮我订 / book a table / restaurant reservation / dinner booking". Checks real availability where possible and returns prefilled booking links — never auto-books.
---

# NZ Dining Reservation Skill (multi-platform)

Help the user reserve a restaurant in **Auckland, NZ** (default region; change only if
they name another city). This skill does NOT auto-book — it **checks real availability
where it can**, then returns **prefilled deep-links** the user opens to confirm.

Backed by `scripts/dining/` (also the `dining` MCP server). OpenTable is intentionally
**off** (near-zero NZ coverage); the live platforms are:

| Provider | Strength | Real availability? | venue_id format |
|----------|----------|--------------------|-----------------|
| **sevenrooms** | Fine dining (SkyCity, Ahi, Esther, Botswana Butchery) | ✅ live JSON | slug, e.g. `botswanabutcheryauckland` |
| **resdiary** | Broad NZ (Savor, Ostro, Nourish) | deep-link (widget shows slots) | `VenueName/VenueId` |
| **firsttable** | Off-peak 50%-off deals | ✅ GraphQL | numeric restaurant id |
| **nowbookit** | Independent venues | deep-link | `accountid[:venueid]` |

## How to run

Prefer the `dining` MCP tools (`dining_check_availability`, `dining_build_booking_link`,
`dining_list_providers`). Otherwise call the package directly:

```bash
PY=/Users/jason.shao/Documents/GitHub1/claude_code_jshao/.venv/bin/python
cd /Users/jason.shao/Documents/GitHub1/claude_code_jshao/scripts
$PY -m dining.core availability sevenrooms <slug> <YYYY-MM-DD> <party> [HH:MM]
$PY -m dining.core link <provider> <venue_id> <YYYY-MM-DDTHH:MM> <party>
```

## Workflow

1. **Parse intent** — cuisine, area (**default Auckland**), date, time, party size.
   Convert "周五晚7点 / this Friday 7pm" → `YYYY-MM-DDTHH:MM` in NZ local time (today's
   date is in context). Ask once if date/time/party is missing.

2. **Find venues + their platform** — providers can't be scraped server-side, so use
   **web search** to find real venues and which platform they use, plus the `venue_id`:
   - SevenRooms: search `sevenrooms.com/explore <restaurant> Auckland` → slug in the URL.
   - ResDiary: `booking.resdiary.com <restaurant>` → `VenueName/VenueId` in the widget URL.
   - First Table: `firsttable.co.nz/auckland <restaurant>`.
   - Now Book It: the venue's own site's booking widget (`bookings.nowbookit.com?accountid=`).
   Never invent ids — confirm from a real URL.

3. **Check availability first** (the important step). For each candidate that supports it
   (SevenRooms, First Table) call `dining_check_availability(provider, venue_id, date,
   party_size, time)`. **Only present venues that actually have a slot** near the
   requested time. For ResDiary / Now Book It (no server-side availability), say
   "availability shown on opening the link".

4. **Present** a tight table — these columns are **required, in this order**:
   restaurant · **provider/platform** · area · **available slots near the time** ·
   **[预订 / Book]** link (from `dining_build_booking_link` or the result's `booking_link`).
   - **Always include the provider/platform column** (e.g. `sevenrooms`, `firsttable`,
     `resdiary`, `nowbookit`) for **every** row — name it even when a venue is off-platform
     (label it e.g. "自有渠道 / direct"). Never omit it; the user relies on knowing which
     platform each booking goes through.
   - In any follow-up re-summary, keep the provider/platform column too — don't drop it
     when compressing.
   If nothing is free near the requested time, say so and offer the nearest slots or
   alternatives — don't pad.

5. **Honesty note** (always):
   > 这些是各平台公开数据；可订时段以打开链接后的页面为最终确认。本工具不替你下单。

6. **Optional logging** — on a confirmed pick, append one line to
   `~/Documents/Dining/bookings.md` (date · restaurant · platform · party · link).

## Guardrails

- Never claim a table is booked — only the opened link confirms it.
- Prefer providers that can verify availability (SevenRooms, First Table) when choosing
  what to surface.
- Never ask for or store logins, card numbers, or payment info.
- Availability endpoints are undocumented/may change — if a check is `degraded`, fall
  back to the deep-link instead of guessing.
