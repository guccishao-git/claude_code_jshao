"""First Table adapter — NZ's most-used booking app (off-peak 50%-off-food deals).

Discovery/deals layer: great for "find a cheap early dinner", not general any-time
booking. Has an open, unauthenticated GraphQL read endpoint (undocumented, no SLA —
may lock down anytime). `venue_id` is the First Table restaurant id used by the API.

  POST https://api.firsttable.net/graphql
  query { allAvailabilitySearch(restaurantIds:[<id>], date:"YYYY-MM-DD", people:<n>) { ... } }
"""

from __future__ import annotations

from typing import Optional

try:
    import httpx
except ImportError:
    httpx = None

from .base import (Provider, Slot, AvailabilityResult, BROWSER_HEADERS, HTTP_TIMEOUT)

GRAPHQL = "https://api.firsttable.net/graphql"
SITE = "https://www.firsttable.co.nz"


def _split_venue_id(venue_id: str):
    """First Table needs two different keys: a numeric restaurantId for the
    availability GraphQL, and a `region/suburb/slug` path for the (only) working
    venue page URL. There is no numeric page route — `/restaurant/<id>` 404s.

    So `venue_id` may carry both, in either order, joined by `|`:
        "6401|auckland/mount-eden/maya-hotpot-dominion-road"
        "auckland/mount-eden/maya-hotpot-dominion-road|6401"
    or just one of them. Returns (numeric_id_or_None, slug_path_or_None).
    """
    numeric, slug = None, None
    for part in str(venue_id).split("|"):
        part = part.strip().strip("/")
        if not part:
            continue
        if part.isdigit():
            numeric = part
        elif "/" in part:
            slug = part
    return numeric, slug

# The endpoint 403s without a same-origin Origin/Referer; restaurantIds is [Int],
# and slots live under `availableTimes` (the old `sessions`/`[ID!]` schema is gone).
_GQL_HEADERS = {
    "Content-Type": "application/json",
    "Origin": SITE,
    "Referer": SITE + "/",
}

_QUERY = """
query Avail($ids: [Int]!, $date: String!, $people: Int!) {
  allAvailabilitySearch(restaurantIds: $ids, date: $date, people: $people) {
    id
    available
    availableTimes { time available deal dealDescription }
  }
}
"""


class FirstTable(Provider):
    name = "firsttable"
    enabled = True
    can_check_availability = True
    home = SITE

    def build_booking_link(self, venue_id: str, datetime_iso: str, party_size: int) -> dict:
        # First Table has no public prefilled /book route AND no numeric-id page
        # route (`/restaurant/<id>` 404s). The only working venue URL is the
        # `region/suburb/slug` path, so a slug is required to build a real link.
        numeric, slug = _split_venue_id(venue_id)
        if slug:
            link = f"{SITE}/{slug}"
            note = "First Table restaurant page (pick the discounted slot on-site)."
        else:
            # Only a numeric id was supplied — we cannot build a working venue page.
            link = f"{SITE}/auckland"
            note = ("No slug path supplied — numeric ids have no working First Table "
                    "page URL. Search this listing for the venue, or re-run with "
                    "venue_id='<region/suburb/slug>|<id>'.")
        return {
            "provider": self.name, "venue_id": venue_id, "datetime": datetime_iso,
            "party_size": int(party_size),
            "links": {"primary": link},
            "note": note,
        }

    def check_availability(self, venue_id: str, date: str, party_size: int,
                           time: Optional[str] = None) -> AvailabilityResult:
        res = AvailabilityResult(provider=self.name, venue_id=venue_id, date=date,
                                 party_size=int(party_size))
        numeric, slug = _split_venue_id(venue_id)
        if slug:
            res.booking_link = f"{SITE}/{slug}"
        if httpx is None or not numeric:
            res.degraded = True
            res.note = ("First Table availability needs a numeric restaurantId; "
                        "open the page to see discounted slots.")
            return res
        try:
            r = httpx.post(GRAPHQL, headers={**BROWSER_HEADERS, **_GQL_HEADERS},
                           json={"query": _QUERY, "variables": {
                               "ids": [int(numeric)], "date": date,
                               "people": int(party_size)}},
                           timeout=HTTP_TIMEOUT)
            payload = r.json()
            rows = (payload.get("data") or {}).get("allAvailabilitySearch") or []
        except Exception as e:
            res.degraded = True
            res.note = f"GraphQL fetch failed ({type(e).__name__}); open the page."
            return res
        if payload.get("errors"):
            res.degraded = True
            res.note = (f"GraphQL error: {payload['errors'][0].get('message')}; "
                        "open the page.")
            return res
        for row in rows:
            for s in row.get("availableTimes", []):
                if s.get("available") and s.get("time"):
                    hhmm = s["time"][:5]
                    label = s.get("dealDescription") or s.get("deal") or "First Table"
                    res.slots.append(Slot(time=hhmm,
                                          datetime_iso=f"{date}T{hhmm}",
                                          bookable=True,
                                          label=label))
        res.slots.sort(key=lambda s: s.time)
        res.available = bool(res.slots)
        res.note = f"{len(res.slots)} bookable slot(s) on {date}."
        return res
