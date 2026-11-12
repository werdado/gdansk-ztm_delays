"""Odczyt zapisów GPS, deduplikacja obserwacji i rozstrzyganie wersji tej samej obserwacji."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from .archive import Capture, read_snapshot
from .timeutil import parse_iso

# (route_short, route_id, trip_id, headsign, vehicle_code, vehicle_service, sched_start,
#  speed, delay, lat, lon, gps_quality, direction)
FIELDS = ("line", "route_id", "trip_id", "headsign", "vehicle_code", "vehicle_service", "sched_start",
          "speed", "delay", "lat", "lon", "gps_quality", "direction")
_MEASURE = ("lat", "lon", "delay", "speed")


@dataclass(slots=True)
class Obs:
    vehicle_id: int
    t: int
    line: str
    route_id: int | None
    trip_id: int | None
    headsign: str | None
    vehicle_code: str | None
    vehicle_service: str | None
    sched_start: int | None
    speed: float | None
    delay: int | None
    lat: float | None
    lon: float | None
    gps_quality: int | None
    direction: int | None
    status: str = "ok"                      # ok | conflict
    reason: str | None = None
    sources: list[int] = field(default_factory=list)
    raw_count: int = 0
    id: int = 0

    @property
    def assigned(self) -> bool:
        return self.trip_id is not None and self.sched_start is not None


def _num(v, cast):
    if v is None or v == "":
        return None
    try:
        return cast(v)
    except (TypeError, ValueError):
        return None


def _text(v):
    return None if v is None or v == "" else str(v)


def normalize(rec: dict) -> tuple | None:
    """Rekord surowy -> (vehicle_id, t, wersja). Zero jest poprawną wartością; puste pole to None."""
    vid = _num(rec.get("vehicleId"), int)
    gen = rec.get("generated")
    if vid is None or not gen:
        return None
    try:
        t = parse_iso(gen)
    except ValueError:
        return None
    sched = rec.get("scheduledTripStartTime")
    version = (
        _text(rec.get("routeShortName")), _num(rec.get("routeId"), int), _num(rec.get("tripId"), int),
        _text(rec.get("headsign")), _text(rec.get("vehicleCode")), _text(rec.get("vehicleService")),
        parse_iso(sched) if sched else None, _num(rec.get("speed"), float), _num(rec.get("delay"), int),
        _num(rec.get("lat"), float), _num(rec.get("lon"), float), _num(rec.get("gpsQuality"), int),
        _num(rec.get("direction"), int),
    )
    return vid, t, version


def resolve(versions: list[tuple]) -> tuple[tuple | None, str | None]:
    """Wersje tej samej obserwacji -> (wybrana wersja, powód konfliktu).

    Różnica wyłącznie w przypisaniu do kursu (jedna wersja z przypisaniem, pozostałe bez żadnego)
    nie jest konfliktem. Różne przypisania lub pomiary to konflikt."""
    if len(versions) == 1:
        return versions[0], None
    idx = {f: i for i, f in enumerate(FIELDS)}
    for m in _MEASURE:
        if len({v[idx[m]] for v in versions}) > 1:
            return None, f"różne pomiary ({m})"
    assigned = [v for v in versions if v[idx["trip_id"]] is not None and v[idx["sched_start"]] is not None]
    if len(assigned) == 1:
        return assigned[0], None
    if len(assigned) == 0:
        # bez przypisania: pozostałe różnice (np. identyfikatory) są nieistotne dla kursu
        return versions[0], None
    return None, "różne przypisania do kursu"


@dataclass
class SourceRec:
    id: int
    capture: Capture
    read_error: str | None = None
    records: int = 0


@dataclass
class IngestResult:
    sources: list[SourceRec]
    observations: list[Obs]
    raw_records: dict[str, int]
    snapshot_errors: int          # zapisy, których nie dało się odczytać
    source_errors: int            # próby, w których źródło nie zapisało odpowiedzi
    bad_records: int = 0          # rekordy wskazanych linii, których nie dało się zinterpretować


def ingest(archive: Path, captures: Iterable[Capture], lines: set[str], start_utc: int, end_utc: int) -> IngestResult:
    sources: list[SourceRec] = []
    groups: dict[tuple[int, int], dict[tuple, list[int]]] = defaultdict(lambda: defaultdict(list))
    raw_in_range: dict[str, int] = defaultdict(int)
    errors = 0
    source_errors = 0
    bad_records = 0
    for cap in captures:
        src = SourceRec(len(sources) + 1, cap)
        sources.append(src)
        if not cap.snapshot_exists or cap.snapshot_key is None:
            src.read_error = "źródło GPS nie zapisało odpowiedzi" if cap.snapshot_key is None else "brak pliku zapisu"
            source_errors += 1
            continue
        try:
            data = read_snapshot(archive, cap.snapshot_key)
            vehicles = data["vehicles"]
        except Exception as e:  # uszkodzony gzip, zły JSON, brak pola
            src.read_error = f"{type(e).__name__}: {e}"
            errors += 1
            continue
        for rec in vehicles:
            if rec.get("routeShortName") not in lines:
                continue
            try:
                n = normalize(rec)
            except (ValueError, TypeError, AttributeError):
                n = None
                bad_records += 1
            if n is None:
                continue
            vid, t, version = n
            if not (start_utc <= t < end_utc):
                continue
            src.records += 1
            raw_in_range[version[0]] += 1
            groups[(vid, t)][version].append(src.id)
    obs: list[Obs] = []
    for (vid, t), vers in groups.items():
        chosen, reason = resolve(list(vers))
        source_ids = sorted({s for ids in vers.values() for s in ids})
        if chosen is None:
            v = next(iter(vers))
            o = Obs(vid, t, *v, status="conflict", reason=reason, sources=source_ids)
        else:
            o = Obs(vid, t, *chosen, sources=source_ids)
        o.raw_count = sum(len(ids) for ids in vers.values())
        obs.append(o)
    obs.sort(key=lambda o: (o.line, o.vehicle_id, o.t))
    for i, o in enumerate(obs, 1):
        o.id = i
    return IngestResult(sources, obs, dict(raw_in_range), errors, source_errors, bad_records)
