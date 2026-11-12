from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from zoneinfo import ZoneInfo

from .params import TIMEZONE

TZ = ZoneInfo(TIMEZONE)
UTC = timezone.utc


def parse_iso(s: str) -> int:
    """ISO-8601 z końcówką Z -> epoch UTC [s]."""
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp())


@lru_cache(maxsize=4096)
def _offset_for_hour(hour_bucket: int) -> int:
    return int(datetime.fromtimestamp(hour_bucket * 3600, TZ).utcoffset().total_seconds())


def local_offset(epoch: int) -> int:
    return _offset_for_hour(epoch // 3600)


def to_local_wall(epoch: int) -> int:
    """Sekundy „ściennego zegara” czasu lokalnego (epoch + przesunięcie)."""
    return epoch + local_offset(epoch)


def local_date(epoch: int) -> date:
    return (datetime(1970, 1, 1) + timedelta(seconds=to_local_wall(epoch))).date()


def day_bounds_utc(d: date) -> tuple[int, int]:
    start = datetime(d.year, d.month, d.day, tzinfo=TZ)
    end = datetime.combine(d + timedelta(days=1), datetime.min.time(), tzinfo=TZ)
    return int(start.timestamp()), int(end.timestamp())


def iso_z(epoch: int) -> str:
    return datetime.fromtimestamp(epoch, UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
