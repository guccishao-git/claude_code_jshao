---
name: pagerduty
description: Query PagerDuty on-call schedules and team rotations using the PagerDuty REST API. Use this skill whenever the user asks who is on call, wants to check a PagerDuty schedule, look up a rotation, find the current on-call person for a team or schedule ID, or asks anything about PagerDuty on-call coverage. Trigger even if the user just says "who's on call?" or "check pagerduty" or mentions a schedule ID.
---

# PagerDuty On-Call Skill

Use the PagerDuty REST API v2 to answer questions about on-call schedules and rotations.

## Authentication

Shell state does not persist between Bash calls in Claude Code, so env vars may not carry over. Always read the token from the config file:

```bash
TOKEN=$(cat ~/.config/pagerduty/token 2>/dev/null || echo "")
```

If the token is empty, tell the user to save their token:
```bash
mkdir -p ~/.config/pagerduty && echo "YOUR_TOKEN" > ~/.config/pagerduty/token && chmod 600 ~/.config/pagerduty/token
```
...and stop there. Never ask the user to type the token into the chat.

## Standard API call pattern

All calls follow this shape:

```bash
curl -s -X GET "https://api.pagerduty.com/<endpoint>" \
  -H "Authorization: Token token=${TOKEN}" \
  -H "Accept: application/vnd.pagerduty+json;version=2"
```

Parse results with `python3 -c "import json,sys; ..."` inline — no need for jq or extra dependencies.

## Known schedules and teams

Use these by default when the user refers to a team by name — no need to ask for IDs:

| Name | Type | ID |
|------|------|----|
| Data Frameworks | Schedule | `PSLVNNV` |

If the user says "frameworks", "data frameworks", or "who's on call for frameworks", use schedule `PSLVNNV`.

## Common queries

### Who is on call for a team?

Use the team ID (e.g. `PF3A4S8`). This returns all escalation policies linked to the team and their current on-call users at each level.

```
GET /oncalls?team_ids[]=<TEAM_ID>&include[]=users
```

Parse: for each entry in `oncalls`, extract `user.name`, `user.email`, `escalation_policy.summary`, and `escalation_level`. Deduplicate by `(user, policy, level)` before displaying.

**Output format:**
```
Team: <team name>
On-call right now:

  [<Policy Name>]
    L1: Alice Smith (asmith@company.com)
    L2: Bob Jones (bjones@company.com)
```

Highlight Level 1 as the primary responder. Group entries by escalation policy for readability.

### Who is on call for a specific schedule?

Use the schedule ID (e.g. `PSLVNNV`). Query a 4-week window from now so the API renders upcoming on-call slots.

```
GET /schedules/<SCHEDULE_ID>?since=<NOW_ISO>&until=<NOW+28DAYS_ISO>&include[]=users
```

Generate `since` and `until` with Python:
```python
from datetime import datetime, timezone, timedelta
now = datetime.now(timezone.utc)
since = now.strftime('%Y-%m-%dT%H:%M:%SZ')
until = (now + timedelta(weeks=4)).strftime('%Y-%m-%dT%H:%M:%SZ')
```

Parse `schedule.final_schedule.rendered_schedule_entries` — each entry has `start`, `end`, and `user.summary`. Mark the current slot (where `start <= now < end`) with "← now".

**Output format — always use a table:**

```
Schedule: Data Frameworks Support Schedule  →  Policy: Data Frameworks (Tier 2)

| # | Engineer         | Start                    | End                      |
|---|------------------|--------------------------|--------------------------|
| 1 | Artur Gukasian   | Mar 7, 2026 12:11 AM PST | Mar 7, 2026  1:11 AM PST | ← now
| 2 | Patrick Barrington| Mar 7, 2026  1:11 AM PST | Mar 7, 2026  2:11 AM PST |
...
```

- Convert all timestamps to PST/PDT (Pacific time) for readability
- Number each row sequentially
- Mark the active row with `← now`
- Always show ALL rows — never truncate, summarize, or collapse any entries
- If `rendered_schedule_entries` is empty, say so clearly — coverage gap or schedule ended

### Look up current user / verify token

```
GET /users/me
```

Use this to confirm the token works and show who is authenticated.

## Output principles

- Always show the person's name and email together
- Convert UTC timestamps to a readable format (e.g. `Mar 7, 2026 10:30 AM UTC`)
- If the user asks about multiple teams or schedules, run the queries and present results grouped clearly
- Keep output concise — the user wants to know who to page, not read a JSON dump
- If the API returns an error (401, 404, etc.), show the error message and suggest a fix (bad token, wrong ID, etc.)

## Set up a single override

**Trigger phrases:** "override [Name] on [date]", "have [Name B] cover for [Name A] on [date]", "setup override", "add override", etc.

A single override replaces one engineer's slot with another person for that time window only.

### Workflow

**Step 1 — Fetch the 4-week schedule** (same as above, use `PSLVNNV` by default)

**Step 2 — Clarify if needed**

If the user hasn't specified all three required pieces, ask before fetching:
- Who is being replaced (the engineer currently scheduled)
- What date (or date range)
- Who should cover instead

**Step 3 — Find the matching slot**

From `rendered_schedule_entries`, find the entry where:
- `user.summary` matches the engineer being replaced (case-insensitive)
- `start` falls on the specified date (PST)

Extract: `start`, `end`, `user.id` of the replacement engineer (look them up via `GET /users?query=<name>` if their ID isn't already in the schedule data).

**Step 4 — Show confirmation preview (ALWAYS before writing)**

```
Proposed override on Data Frameworks Support Schedule:

  Currently scheduled: Mike Trienis
  Date/Time: Mar 13, 8:00 AM PST → Mar 13, 4:00 PM PST

  Override: Patrick Barrington will cover instead.

Confirm? (yes/no)
```

**Step 5 — POST the override**

```bash
TOKEN=$(cat ~/.config/pagerduty/token 2>/dev/null || echo "")
curl -s -X POST "https://api.pagerduty.com/schedules/PSLVNNV/overrides" \
  -H "Authorization: Token token=${TOKEN}" \
  -H "Accept: application/vnd.pagerduty+json;version=2" \
  -H "Content-Type: application/json" \
  -d '{
    "override": {
      "start": "<SLOT_START_ISO>",
      "end":   "<SLOT_END_ISO>",
      "user":  {"id": "<REPLACEMENT_USER_ID>", "type": "user_reference"}
    }
  }'
```

**Step 6 — Confirm success**

```
Override created!

Patrick Barrington covers: Mar 13, 8:00 AM PST → Mar 13, 4:00 PM PST (ID: <override_id>)

Override is live in PagerDuty.
```

### Look up a user ID by name

If the replacement engineer isn't in the current schedule window, fetch their user ID:

```bash
TOKEN=$(cat ~/.config/pagerduty/token 2>/dev/null || echo "")
curl -s "https://api.pagerduty.com/users?query=<name>" \
  -H "Authorization: Token token=${TOKEN}" \
  -H "Accept: application/vnd.pagerduty+json;version=2"
```

Parse `users[0].id` from the response.

---

## Swap two engineers' on-call slots

**Trigger phrases:** "swap [Name] on [date] with [Name] on [date]", "swap [Name A] and [Name B]", "can you swap X and Y", etc.

PagerDuty swaps are implemented as **schedule overrides** — temporary assignments that override the base rotation without modifying it permanently.

### Workflow

**Step 1 — Fetch the 4-week schedule**

Reuse the existing schedule query for `PSLVNNV` (or whichever schedule ID is relevant):

```bash
TOKEN=$(cat ~/.config/pagerduty/token 2>/dev/null || echo "")
curl -s "https://api.pagerduty.com/schedules/PSLVNNV?since=<NOW_ISO>&until=<NOW+28DAYS_ISO>&include[]=users" \
  -H "Authorization: Token token=${TOKEN}" \
  -H "Accept: application/vnd.pagerduty+json;version=2"
```

**Step 2 — Find matching slots**

From `schedule.final_schedule.rendered_schedule_entries`, locate the two entries:
- Match engineer name **case-insensitively** against `user.summary`
- Match date against the `start` timestamp (same calendar day in PST)

Extract from each matching entry: `start`, `end`, `user.summary`, `user.id`

**Edge cases — stop and tell the user if:**
- Engineer name not found in that schedule
- No entry on that date for that engineer
- Multiple entries for the same engineer on the same date → list them and ask which one to use

**Step 3 — Show confirmation preview (ALWAYS before writing)**

```
Proposed swap on Data Frameworks Support Schedule:

  Mike Trienis:        Mar 13, 8:00 AM PST → Mar 13, 4:00 PM PST
  Patrick Barrington:  Mar 15, 8:00 AM PST → Mar 15, 4:00 PM PST

After swap:
  Patrick Barrington covers: Mar 13, 8:00 AM PST → Mar 13, 4:00 PM PST
  Mike Trienis covers:       Mar 15, 8:00 AM PST → Mar 15, 4:00 PM PST

Confirm? (yes/no)
```

Do NOT proceed until the user explicitly confirms with "yes" or equivalent.

**Step 4 — POST two overrides**

On confirmation, create two overrides (one per slot):

```bash
TOKEN=$(cat ~/.config/pagerduty/token 2>/dev/null || echo "")

# Override slot A's time window → assign user B
curl -s -X POST "https://api.pagerduty.com/schedules/PSLVNNV/overrides" \
  -H "Authorization: Token token=${TOKEN}" \
  -H "Accept: application/vnd.pagerduty+json;version=2" \
  -H "Content-Type: application/json" \
  -d '{
    "override": {
      "start": "<SLOT_A_START_ISO>",
      "end":   "<SLOT_A_END_ISO>",
      "user":  {"id": "<USER_B_ID>", "type": "user_reference"}
    }
  }'

# Override slot B's time window → assign user A
curl -s -X POST "https://api.pagerduty.com/schedules/PSLVNNV/overrides" \
  -H "Authorization: Token token=${TOKEN}" \
  -H "Accept: application/vnd.pagerduty+json;version=2" \
  -H "Content-Type: application/json" \
  -d '{
    "override": {
      "start": "<SLOT_B_START_ISO>",
      "end":   "<SLOT_B_END_ISO>",
      "user":  {"id": "<USER_A_ID>", "type": "user_reference"}
    }
  }'
```

Use the exact `start`/`end` ISO strings from the rendered schedule entries (they are already in UTC).

**Step 5 — Confirm success**

Parse both responses. If successful (HTTP 201), show:

```
Swap complete!

Override 1: Patrick Barrington covers Mar 13 (ID: <override_id>)
Override 2: Mike Trienis covers Mar 15 (ID: <override_id>)

Both overrides are live in PagerDuty. Re-query the schedule to verify.
```

If either POST fails, show the error body and do not proceed with the second override.
