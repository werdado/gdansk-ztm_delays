"""Odczyt archiwum: manifesty, zapisy GPS, wybór pełnych dób lokalnych. Archiwum nie jest modyfikowane."""
from __future__ import annotations

import gzip
import json
import os
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

from .params import Params
from .timeutil import day_bounds_utc, local_date, parse_iso


@dataclass
class Capture:
    """Jedna próba pobrania źródła GPS: zapis i/lub manifest."""
    snapshot_key: str | None
    manifest_key: str | None
    slot: int                      # planowany moment (epoch UTC)
    run_status: str | None = None
    source_status: str | None = None
    url: str | None = None
    fetched_at: str | None = None
    received_at: str | None = None
    stored_at: str | None = None
    snapshot_exists: bool = False

    @property
    def provenance_gap(self) -> bool:
        return self.manifest_key is None


def _slot_from_name(name: str) -> int:
    return parse_iso(name)


def scan(archive: Path) -> list[Capture]:
    archive = Path(archive)
    caps: dict[str, Capture] = {}
    by_manifest_key: list[tuple[str, dict]] = []
    runs = archive / "runs"
    if runs.is_dir():
        for date_dir in sorted(os.scandir(runs), key=lambda e: e.name):
            if not date_dir.is_dir():
                continue
            for slot_dir in sorted(os.scandir(date_dir.path), key=lambda e: e.name):
                if not slot_dir.is_dir():
                    continue
                for f in sorted(os.scandir(slot_dir.path), key=lambda e: e.name):
                    if not f.name.endswith(".json"):
                        continue
                    mkey = f"runs/{date_dir.name}/{slot_dir.name}/{f.name}"
                    try:
                        m = json.loads(Path(f.path).read_text())
                    except (OSError, ValueError):
                        m = None
                    by_manifest_key.append((mkey, m))
    for mkey, m in by_manifest_key:
        slot_name = mkey.split("/")[2]
        try:
            slot = _slot_from_name(slot_name)
        except ValueError:
            continue
        gps = None
        if isinstance(m, dict):
            for s in m.get("sources", []):
                if s.get("source") == "gps":
                    gps = s
        if gps is None:
            # manifest bez źródła GPS (np. slot_expired) – tylko próba pobrania obejmująca czas
            caps[mkey] = Capture(None, mkey, slot, run_status=(m or {}).get("status"))
            continue
        key = gps.get("key")
        cap = Capture(key, mkey, slot, run_status=m.get("status"), source_status=gps.get("status"),
                      url=gps.get("url"), fetched_at=gps.get("fetchedAt"), received_at=gps.get("receivedAt"),
                      stored_at=gps.get("storedAt"))
        caps[key or mkey] = cap
    snaps = archive / "snapshots" / "gps"
    if snaps.is_dir():
        for date_dir in sorted(os.scandir(snaps), key=lambda e: e.name):
            if not date_dir.is_dir():
                continue
            for slot_dir in sorted(os.scandir(date_dir.path), key=lambda e: e.name):
                if not slot_dir.is_dir():
                    continue
                for f in sorted(os.scandir(slot_dir.path), key=lambda e: e.name):
                    if not f.name.endswith(".json.gz"):
                        continue
                    key = f"snapshots/gps/{date_dir.name}/{slot_dir.name}/{f.name}"
                    if key in caps:
                        caps[key].snapshot_exists = True
                    else:
                        try:
                            slot = _slot_from_name(slot_dir.name)
                        except ValueError:
                            continue
                        caps[key] = Capture(key, None, slot, snapshot_exists=True)
    return sorted(caps.values(), key=lambda c: (c.slot, c.snapshot_key or c.manifest_key or ""))


@dataclass
class DaySelection:
    days: list[date]
    skipped: list[dict] = field(default_factory=list)

    @property
    def start_utc(self) -> int:
        return day_bounds_utc(self.days[0])[0]

    @property
    def end_utc(self) -> int:
        return day_bounds_utc(self.days[-1])[1]


def select_days(captures: list[Capture], params: Params, date_from: date | None = None,
                date_to: date | None = None) -> DaySelection:
    """Doba jest pełna, gdy próby pobrania obejmują ją od początku do końca."""
    if not captures:
        raise SystemExit("Brak prób pobrania w archiwum.")
    slots_by_day: dict[date, list[int]] = {}
    for c in captures:
        slots_by_day.setdefault(local_date(c.slot), []).append(c.slot)
    first, last = min(slots_by_day), max(slots_by_day)
    days, skipped = [], []
    d = first
    while d <= last:
        slots = slots_by_day.get(d)
        start, end = day_bounds_utc(d)
        if not slots:
            skipped.append({"date": d.isoformat(), "reason": "brak prób pobrania"})
        elif min(slots) > start + params.day_tolerance_s:
            skipped.append({"date": d.isoformat(), "reason": "niepełna doba: pierwsza próba po początku doby"})
        elif max(slots) < end - params.day_tolerance_s:
            skipped.append({"date": d.isoformat(), "reason": "niepełna doba: ostatnia próba przed końcem doby"})
        else:
            days.append(d)
        d += timedelta(days=1)
    if date_from or date_to:
        days = [d for d in days if (not date_from or d >= date_from) and (not date_to or d <= date_to)]
    if not days:
        raise SystemExit("Brak pełnych dób do przetworzenia w wybranym zakresie.")
    for a, b in zip(days, days[1:]):
        if (b - a).days != 1:
            raise SystemExit("Pełne doby nie tworzą ciągłego zakresu: " + f"{a} i {b} są rozdzielone niepełną dobą.")
    return DaySelection(days, skipped)


def read_snapshot(archive: Path, key: str) -> dict:
    with gzip.open(Path(archive) / key, "rb") as f:
        return json.loads(f.read())
