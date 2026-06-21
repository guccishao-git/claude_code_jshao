"""Now Book It adapter — broad coverage of independent Auckland venues.

Stable widget deep-links. `venue_id` is "accountid" or "accountid:venueid" (GUIDs from
the venue's embedded booking widget). No public availability API, so the link is the
live availability view.

  https://bookings.nowbookit.com/?accountid=<GUID>&venueid=<id>&covers=<n>&date=<YYYY-MM-DD>&time=<HH:MM>
"""

from __future__ import annotations

from urllib.parse import urlencode

from .base import Provider, split_datetime

WIDGET = "https://bookings.nowbookit.com/"


class NowBookIt(Provider):
    name = "nowbookit"
    enabled = True
    can_check_availability = False
    home = "https://nowbookit.com"

    def build_booking_link(self, venue_id: str, datetime_iso: str, party_size: int) -> dict:
        date, time = split_datetime(datetime_iso)
        account, _, venue = venue_id.partition(":")
        params = {"accountid": account, "covers": int(party_size), "date": date, "time": time}
        if venue:
            params["venueid"] = venue
        link = WIDGET + "?" + urlencode(params)
        return {
            "provider": self.name, "venue_id": venue_id, "datetime": datetime_iso,
            "party_size": int(party_size),
            "links": {"primary": link},
            "note": ("Now Book It widget deep-link. venue_id is 'accountid' or "
                     "'accountid:venueid' (GUIDs from the venue's booking widget)."),
        }
