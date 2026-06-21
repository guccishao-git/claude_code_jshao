"""NZ dining-reservation assistant — aggregator over booking-platform providers.

Default region: Auckland, New Zealand. No provider auto-books; this layer finds
real bookable slots where it can (SevenRooms / First Table) and otherwise builds a
prefilled deep-link the user opens to finish. OpenTable is disabled by default
(near-zero NZ coverage).

CLI:
  python core.py providers
  python core.py availability sevenrooms botswanabutcheryauckland 2026-06-26 2 19:00
  python core.py link resdiary "Ostro/1234" 2026-06-26T19:00 2
"""

from __future__ import annotations

import json
import sys
from typing import Optional

try:
    from .providers import REGISTRY, ALL_PROVIDERS
except ImportError:  # run as a script (no package context)
    import os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from dining.providers import REGISTRY, ALL_PROVIDERS


def list_providers(include_disabled: bool = False) -> list[dict]:
    return [
        {"name": p.name, "enabled": p.enabled,
         "can_check_availability": p.can_check_availability, "home": p.home}
        for p in ALL_PROVIDERS if include_disabled or p.enabled
    ]


def enabled_provider_names() -> list[str]:
    return [p.name for p in ALL_PROVIDERS if p.enabled]


def _get(provider: str):
    p = REGISTRY.get(provider)
    if p is None:
        raise ValueError(f"unknown provider {provider!r}; known: {list(REGISTRY)}")
    return p


def check_availability(provider: str, venue_id: str, date: str, party_size: int,
                       time: Optional[str] = None) -> dict:
    """Return real bookable slots for one venue on one provider (where supported)."""
    return _get(provider).check_availability(venue_id, date, int(party_size), time).to_dict()


def build_booking_link(provider: str, venue_id: str, datetime_iso: str,
                       party_size: int) -> dict:
    """Build a prefilled booking deep-link for one venue on one provider."""
    return _get(provider).build_booking_link(venue_id, datetime_iso, int(party_size))


def search(query: str, location: str = "Auckland", cuisine: Optional[str] = None,
           providers: Optional[list[str]] = None, limit: int = 5) -> dict:
    """Best-effort discovery across enabled providers.

    Most providers can't be scraped server-side, so this usually returns degraded;
    the orchestrating skill should fall back to web search to find a venue_id, then
    call check_availability/build_booking_link here.
    """
    names = providers or enabled_provider_names()
    out = {"location": location, "results": [], "degraded_all": True}
    for name in names:
        try:
            r = _get(name).search(query, location, cuisine=cuisine, limit=limit)
        except Exception as e:
            r = {"provider": name, "restaurants": [], "degraded": True,
                 "note": f"{type(e).__name__}: {e}"}
        out["results"].append(r)
        if not r.get("degraded"):
            out["degraded_all"] = False
    if out["degraded_all"]:
        out["note"] = ("No server-side discovery available — use web search to find a "
                       "venue on one of: " + ", ".join(names) +
                       ", then call check_availability/build_booking_link with its venue_id.")
    return out


# ---------------------------------------------------------------------------
if __name__ == "__main__":
    a = sys.argv[1:]
    cmd = a[0] if a else "help"
    if cmd == "providers":
        print(json.dumps(list_providers(include_disabled=True), indent=2))
    elif cmd == "availability" and len(a) >= 5:
        print(json.dumps(check_availability(a[1], a[2], a[3], int(a[4]),
              a[5] if len(a) > 5 else None), indent=2, ensure_ascii=False))
    elif cmd == "link" and len(a) >= 5:
        print(json.dumps(build_booking_link(a[1], a[2], a[3], int(a[4])),
              indent=2, ensure_ascii=False))
    elif cmd == "search" and len(a) >= 2:
        print(json.dumps(search(a[1], a[2] if len(a) > 2 else "Auckland",
              cuisine=a[3] if len(a) > 3 else None), indent=2, ensure_ascii=False))
    else:
        print("usage:\n  core.py providers\n"
              "  core.py availability <provider> <venue_id> <YYYY-MM-DD> <party> [HH:MM]\n"
              "  core.py link <provider> <venue_id> <YYYY-MM-DDTHH:MM> <party>\n"
              "  core.py search <query> [location] [cuisine]")
