"""OpenTable adapter — DISABLED by default.

OpenTable has near-zero Auckland coverage (~4 venues vs 1000+), so it is not part of
the default NZ flow. Kept as an adapter for completeness / occasional tourist venues.
Deep-link only (no public API). `venue_id` is a restaurant slug or numeric rid.
"""

from __future__ import annotations

from urllib.parse import urlencode

from .base import Provider, split_datetime

PAGE = "https://www.opentable.com/r/{slug}"
RESTREF = "https://www.opentable.com/restref/client/"


class OpenTable(Provider):
    name = "opentable"
    enabled = False  # near-zero NZ coverage — off by default
    can_check_availability = False
    home = "https://www.opentable.com"

    def build_booking_link(self, venue_id: str, datetime_iso: str, party_size: int) -> dict:
        date, time = split_datetime(datetime_iso)
        dt = f"{date}T{time}"
        links = {}
        if str(venue_id).isdigit():
            links["primary"] = RESTREF + "?" + urlencode(
                {"rid": venue_id, "restref": venue_id, "dateTime": dt,
                 "partySize": int(party_size), "lang": "en-NZ"})
        else:
            links["primary"] = PAGE.format(slug=venue_id) + "?" + urlencode(
                {"dateTime": dt, "covers": int(party_size)})
        return {
            "provider": self.name, "venue_id": venue_id, "datetime": datetime_iso,
            "party_size": int(party_size), "links": links,
            "note": "OpenTable deep-link (sparse NZ coverage; disabled by default).",
        }
