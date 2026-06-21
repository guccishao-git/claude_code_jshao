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

_QUERY = """
query Avail($ids: [ID!]!, $date: String!, $people: Int!) {
  allAvailabilitySearch(restaurantIds: $ids, date: $date, people: $people) {
    restaurantId
    sessions { time available price }
  }
}
"""


class FirstTable(Provider):
    name = "firsttable"
    enabled = True
    can_check_availability = True
    home = SITE

    def build_booking_link(self, venue_id: str, datetime_iso: str, party_size: int) -> dict:
        # First Table has no public prefilled /book route; link to the restaurant page.
        # `venue_id` here may be a "region/suburb/slug" path or a numeric id.
        path = venue_id if "/" in venue_id else f"restaurant/{venue_id}"
        link = f"{SITE}/{path.strip('/')}"
        return {
            "provider": self.name, "venue_id": venue_id, "datetime": datetime_iso,
            "party_size": int(party_size),
            "links": {"primary": link},
            "note": "First Table restaurant page (pick the discounted slot on-site).",
        }

    def check_availability(self, venue_id: str, date: str, party_size: int,
                           time: Optional[str] = None) -> AvailabilityResult:
        res = AvailabilityResult(provider=self.name, venue_id=venue_id, date=date,
                                 party_size=int(party_size))
        if httpx is None or not str(venue_id).isdigit():
            res.degraded = True
            res.note = ("First Table availability needs a numeric restaurantId; "
                        "open the page to see discounted slots.")
            return res
        try:
            r = httpx.post(GRAPHQL, headers={**BROWSER_HEADERS,
                           "Content-Type": "application/json"},
                           json={"query": _QUERY, "variables": {
                               "ids": [venue_id], "date": date, "people": int(party_size)}},
                           timeout=HTTP_TIMEOUT)
            rows = (r.json().get("data") or {}).get("allAvailabilitySearch") or []
        except Exception as e:
            res.degraded = True
            res.note = f"GraphQL fetch failed ({type(e).__name__}); open the page."
            return res
        for row in rows:
            for s in row.get("sessions", []):
                if s.get("available") and s.get("time"):
                    res.slots.append(Slot(time=s["time"][:5],
                                          datetime_iso=f"{date}T{s['time'][:5]}",
                                          bookable=True,
                                          label="First Table discount"))
        res.slots.sort(key=lambda s: s.time)
        res.available = bool(res.slots)
        res.note = f"{len(res.slots)} discounted slot(s) on {date}."
        return res
