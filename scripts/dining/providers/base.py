"""Provider interface + shared data types for the NZ dining-reservation assistant.

Each booking platform (SevenRooms, ResDiary, First Table, Now Book It, OpenTable)
is a Provider subclass implementing some of:
  - search()             best-effort restaurant discovery
  - check_availability() real bookable time slots (the key capability)
  - build_booking_link() prefilled deep-link the user opens to finish booking

No provider auto-books. Anything not implemented degrades gracefully rather than
raising, so the orchestrating skill can fall back (e.g. to web search).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-NZ,en;q=0.9",
}
HTTP_TIMEOUT = 20.0


@dataclass
class Restaurant:
    name: str
    provider: str
    venue_id: str  # provider-specific: slug, "Name/Id", or numeric id
    url: Optional[str] = None
    area: Optional[str] = None
    cuisine: Optional[str] = None

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class Slot:
    time: str            # "HH:MM"
    datetime_iso: str    # "YYYY-MM-DDTHH:MM"
    bookable: bool = True
    label: Optional[str] = None   # e.g. "Reservation | Dinner", or "request only"

    def to_dict(self) -> dict:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class AvailabilityResult:
    provider: str
    venue_id: str
    date: str
    party_size: int
    available: bool = False
    slots: list = field(default_factory=list)   # list[Slot]
    booking_link: Optional[str] = None
    degraded: bool = False
    note: str = ""

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "venue_id": self.venue_id,
            "date": self.date,
            "party_size": self.party_size,
            "available": self.available,
            "slots": [s.to_dict() for s in self.slots],
            "booking_link": self.booking_link,
            "degraded": self.degraded,
            "note": self.note,
        }


class Provider:
    """Base provider. Subclasses set `name` and override what they support."""

    name: str = "base"
    enabled: bool = True
    can_check_availability: bool = False
    home: str = ""

    # -- capabilities (override as supported) -------------------------------
    def search(self, query: str, location: str = "Auckland",
               cuisine: Optional[str] = None, limit: int = 5) -> dict:
        return {"provider": self.name, "restaurants": [], "degraded": True,
                "note": f"{self.name}: search not implemented; use web search to find a venue id."}

    def check_availability(self, venue_id: str, date: str, party_size: int,
                           time: Optional[str] = None) -> AvailabilityResult:
        return AvailabilityResult(
            provider=self.name, venue_id=venue_id, date=date, party_size=party_size,
            degraded=True,
            note=f"{self.name}: availability check not supported — open the booking link to see slots.",
            booking_link=self._safe_link(venue_id, date, time, party_size),
        )

    def build_booking_link(self, venue_id: str, datetime_iso: str, party_size: int) -> dict:
        raise NotImplementedError

    # -- helpers ------------------------------------------------------------
    def _safe_link(self, venue_id, date, time, party_size):
        try:
            dt = f"{date}T{time}" if time else f"{date}T19:00"
            return self.build_booking_link(venue_id, dt, party_size)["links"]["primary"]
        except Exception:
            return None


def validate_datetime(dt: str) -> None:
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}", dt):
        raise ValueError(f"datetime must be 'YYYY-MM-DDTHH:MM', got: {dt!r}")


def split_datetime(dt: str) -> tuple[str, str]:
    validate_datetime(dt)
    date, time = dt.split("T")
    return date, time
