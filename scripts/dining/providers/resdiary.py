"""ResDiary adapter — best-documented deep-link of all NZ platforms.

Large NZ footprint (Savor Group, Ostro, Nourish Group). Booking widget deep-link is
officially documented and prefillable:
  https://booking.resdiary.com/widget/Standard/<VenueName>/<VenueId>?date=YYYY-MM-DD&time=HH:MM&partySize=N

`venue_id` for this provider is the "VenueName/VenueId" pair, e.g. "RipplesatChowderBay/5283".
Real-time availability requires the partner ConsumerApi (OAuth) — not done here — so
check_availability degrades to "open the link", which is itself a live availability view.
"""

from __future__ import annotations

from urllib.parse import urlencode

from .base import Provider, split_datetime

WIDGET = "https://booking.resdiary.com/widget/Standard/{venue}"


class ResDiary(Provider):
    name = "resdiary"
    enabled = True
    can_check_availability = False  # would need partner ConsumerApi (OAuth)
    home = "https://www.resdiary.com"

    def build_booking_link(self, venue_id: str, datetime_iso: str, party_size: int) -> dict:
        date, time = split_datetime(datetime_iso)
        venue = venue_id.strip("/")  # expects "VenueName/VenueId"
        q = urlencode({"date": date, "time": time, "partySize": int(party_size)})
        link = WIDGET.format(venue=venue) + "?" + q
        return {
            "provider": self.name, "venue_id": venue_id, "datetime": datetime_iso,
            "party_size": int(party_size),
            "links": {"primary": link},
            "note": ("Official ResDiary widget deep-link (prefilled). venue_id must be "
                     "'VenueName/VenueId'. The widget shows live availability on open."),
        }
