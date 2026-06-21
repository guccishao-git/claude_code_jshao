"""Booking-platform adapters for the NZ dining assistant."""

from .base import Provider, Restaurant, Slot, AvailabilityResult  # noqa: F401
from .sevenrooms import SevenRooms
from .resdiary import ResDiary
from .firsttable import FirstTable
from .nowbookit import NowBookIt
from .opentable import OpenTable

# Registry, in default Auckland priority order.
ALL_PROVIDERS = [SevenRooms(), ResDiary(), FirstTable(), NowBookIt(), OpenTable()]
REGISTRY = {p.name: p for p in ALL_PROVIDERS}
