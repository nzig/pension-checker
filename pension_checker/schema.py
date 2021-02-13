from datetime import date, datetime
from decimal import Decimal
from enum import IntEnum
from typing import Any


class SugHafrasha(IntEnum):
    pitzuim = 1
    tagmulim_oved = 2
    tagmulim_maavid = 3
    kh_oved = 8
    kh_maavid = 9


HAFRASHA_RANGES_PENSION = {
    SugHafrasha.pitzuim: (Decimal("6.0"), Decimal("8.33")),
    SugHafrasha.tagmulim_oved: (Decimal("6.0"), Decimal("7.0")),
    SugHafrasha.tagmulim_maavid: (Decimal("6.5"), Decimal("7.5")),
}


def parse_datetime(date_str: str) -> datetime:
    return datetime.strptime(date_str, "%Y%m%d%H%M%S")


def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str, "%Y%m%d").date()


def fix_nil(element: Any, default: Any = None) -> Any:
    if isinstance(element, dict):
        if len(element) == 1:
            [key] = element
            if isinstance(key, str) and key.endswith("nil"):
                return default
    return element
