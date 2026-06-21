"""SevenRooms adapter — the strongest NZ fit.

Powers Auckland fine-dining (SkyCity group, Ahi, Esther, Botswana Butchery, etc.).
Has an UNAUTHENTICATED availability JSON endpoint (verified live), so this provider
can actually answer "is there a table?" before handing back a deep-link.

Availability endpoint (internal/undocumented, may change without notice):
  GET https://www.sevenrooms.com/api-yoa/availability/widget/range
      ?venue=<slug>&party_size=<n>&start_date=<YYYY-MM-DD>&num_days=1
      &channel=SEVENROOMS_WIDGET&halo_size_interval=16
Slots live at data.data.availability[date][*].times[*] with type "book"/"request".
"""

from __future__ import annotations

from typing import Optional
from urllib.parse import urlencode

try:
    import httpx
except ImportError:
    httpx = None

from .base import (Provider, Slot, AvailabilityResult, BROWSER_HEADERS,
                   HTTP_TIMEOUT, split_datetime)

AVAIL_URL = "https://www.sevenrooms.com/api-yoa/availability/widget/range"
EXPLORE = "https://www.sevenrooms.com/explore/{venue}/reservations/create/search"


class SevenRooms(Provider):
    name = "sevenrooms"
    enabled = True
    can_check_availability = True
    home = "https://www.sevenrooms.com"

    def build_booking_link(self, venue_id: str, datetime_iso: str, party_size: int) -> dict:
        date, time = split_datetime(datetime_iso)
        q = urlencode({"date": date, "party_size": int(party_size), "start_time": time,
                       "halo_size_interval": 16})
        link = EXPLORE.format(venue=venue_id) + "?" + q
        return {
            "provider": self.name, "venue_id": venue_id, "datetime": datetime_iso,
            "party_size": int(party_size),
            "links": {"primary": link},
            "note": "Lands on the SevenRooms slot picker prefilled with date/time/party.",
        }

    def check_availability(self, venue_id: str, date: str, party_size: int,
                           time: Optional[str] = None) -> AvailabilityResult:
        res = AvailabilityResult(provider=self.name, venue_id=venue_id, date=date,
                                 party_size=int(party_size))
        res.booking_link = self.build_booking_link(
            venue_id, f"{date}T{time or '19:00'}", party_size)["links"]["primary"]

        if httpx is None:
            res.degraded = True
            res.note = "httpx not installed."
            return res

        params = {"venue": venue_id, "party_size": int(party_size), "start_date": date,
                  "num_days": 1, "channel": "SEVENROOMS_WIDGET", "halo_size_interval": 16}
        try:
            r = httpx.get(AVAIL_URL, params=params, headers=BROWSER_HEADERS,
                          timeout=HTTP_TIMEOUT, follow_redirects=True)
            data = r.json()
        except Exception as e:
            res.degraded = True
            res.note = f"availability fetch failed ({type(e).__name__}); open link to check."
            return res

        day = (data.get("data", {}).get("availability", {}) or {}).get(date, [])
        seen: set[str] = set()
        for block in day:
            label = block.get("name")
            for t in block.get("times", []):
                tm = t.get("time")
                ttype = t.get("type")  # "book" | "request" | "closed"
                if not tm or ttype not in ("book", "request") or tm in seen:
                    continue
                seen.add(tm)
                res.slots.append(Slot(
                    time=tm, datetime_iso=f"{date}T{tm}",
                    bookable=(ttype == "book"),
                    label=(t.get("public_time_slot_description") or label or None)
                    + ("" if ttype == "book" else " (request only)"),
                ))
        res.slots.sort(key=lambda s: s.time)
        res.available = any(s.bookable for s in res.slots)
        if time:
            near = [s for s in res.slots if _within(s.time, time, 90)]
            res.note = (f"{len(res.slots)} slot(s) on {date}; "
                        f"{len(near)} within 90min of {time}.")
        else:
            res.note = f"{len(res.slots)} slot(s) on {date}."
        return res


def _within(a: str, b: str, minutes: int) -> bool:
    def m(x):
        h, mm = x.split(":")
        return int(h) * 60 + int(mm)
    return abs(m(a) - m(b)) <= minutes
