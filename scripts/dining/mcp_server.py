#!/usr/bin/env python3
"""NZ dining-reservation assistant — MCP server (stdio).

Multi-platform: SevenRooms, ResDiary, First Table, Now Book It (OpenTable disabled).
Default region Auckland, NZ. Never auto-books — checks real availability where it can
and returns prefilled deep-links for the user to confirm.

Smoke test:  python mcp_server.py --selftest
Registered for Claude Code via the repo-root .mcp.json.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow `import dining.core` whether launched from repo root or here.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dining import core  # noqa: E402

from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP("dining")


@mcp.tool()
def dining_list_providers() -> list:
    """List supported booking platforms and which can check real availability."""
    return core.list_providers(include_disabled=True)


@mcp.tool()
def dining_check_availability(
    provider: str, venue_id: str, date: str, party_size: int, time: str | None = None
) -> dict:
    """Check REAL bookable time slots for a venue on a provider (where supported).

    Args:
        provider: One of sevenrooms | resdiary | firsttable | nowbookit (| opentable).
        venue_id: Provider-specific id — SevenRooms slug (e.g. "botswanabutcheryauckland"),
            ResDiary "VenueName/VenueId", First Table numeric id, Now Book It
            "accountid[:venueid]".
        date: "YYYY-MM-DD".
        party_size: Number of diners.
        time: Optional "HH:MM" to rank slots near a preferred time.

    Returns slots + `available` + a prefilled `booking_link`. If `degraded` is True the
    provider can't be queried server-side — open the booking_link to see live slots.
    """
    return core.check_availability(provider, venue_id, date, party_size, time)


@mcp.tool()
def dining_build_booking_link(
    provider: str, venue_id: str, datetime_iso: str, party_size: int
) -> dict:
    """Build a prefilled booking deep-link the user opens to finish the reservation.

    Args:
        provider: sevenrooms | resdiary | firsttable | nowbookit | opentable.
        venue_id: Provider-specific id (see dining_check_availability).
        datetime_iso: "YYYY-MM-DDTHH:MM".
        party_size: Number of diners.
    """
    return core.build_booking_link(provider, venue_id, datetime_iso, party_size)


@mcp.tool()
def dining_search(
    query: str, location: str = "Auckland", cuisine: str | None = None, limit: int = 5
) -> dict:
    """Best-effort restaurant discovery across providers (default Auckland).

    Usually returns degraded (platforms block server-side scraping) — when so, use web
    search to find a venue on a supported platform, then call dining_check_availability
    / dining_build_booking_link with that venue_id.
    """
    return core.search(query, location, cuisine=cuisine, limit=limit)


def _selftest() -> int:
    avail = core.check_availability(
        "sevenrooms", "botswanabutcheryauckland", "2026-06-26", 2, "19:00")
    print("sevenrooms available:", avail["available"], "| slots:", len(avail["slots"]))
    link = core.build_booking_link("resdiary", "Ostro/1234", "2026-06-26T19:00", 2)
    assert link["links"]["primary"].startswith("https://booking.resdiary.com")
    print("providers:", ", ".join(core.enabled_provider_names()))
    print("selftest OK")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    mcp.run()
