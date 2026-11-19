"""Pomocniczy rozkład GTFS: warianty (trasa, słupki, geometria, kierunek). Kalendarz nie ogranicza analizy."""
from __future__ import annotations

import csv
import hashlib
import io
import zipfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Stop:
    stop_id: str
    name: str
    lat: float
    lon: float


@dataclass
class GtfsVariant:
    route_id: int
    variant: int
    direction: int | None = None
    headsign: str = ""
    status: str = "ok"                      # ok | ambiguous
    note: str = ""
    stops: list[Stop] = field(default_factory=list)
    shape: list[tuple[float, float]] = field(default_factory=list)   # (lat, lon)

    @property
    def key(self) -> str:
        return f"{self.route_id}-{self.variant}"


@dataclass
class Gtfs:
    route_ids: dict[str, set[int]]          # routeShortName -> route_id
    variants: dict[tuple[int, int], GtfsVariant]
    feed_end_date: str | None
    sha256: str
    size: int


def _rows(z: zipfile.ZipFile, name: str):
    with z.open(name) as raw:
        yield from csv.DictReader(io.TextIOWrapper(raw, encoding="utf-8-sig", newline=""))


def _file_hash(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load(path: Path, lines: set[str]) -> Gtfs:
    path = Path(path)
    with zipfile.ZipFile(path) as z:
        route_ids: dict[str, set[int]] = defaultdict(set)
        for r in _rows(z, "routes.txt"):
            if r["route_short_name"] in lines:
                route_ids[r["route_short_name"]].add(int(r["route_id"]))
        wanted = {rid for ids in route_ids.values() for rid in ids}
        trips: dict[str, tuple[int, int, str, int | None, str]] = {}
        for t in _rows(z, "trips.txt"):
            rid = int(t["route_id"])
            if rid not in wanted:
                continue
            parts = t["trip_id"].split("_")
            if len(parts) != 3 or not parts[1].isdigit():
                continue
            direction = int(t["direction_id"]) if t.get("direction_id", "") != "" else None
            trips[t["trip_id"]] = (rid, int(parts[1]), t.get("trip_headsign", ""), direction, t.get("shape_id", ""))
        seqs: dict[str, list[tuple[int, str]]] = defaultdict(list)
        for st in _rows(z, "stop_times.txt"):
            if st["trip_id"] in trips:
                seqs[st["trip_id"]].append((int(st["stop_sequence"]), st["stop_id"]))
        stop_ids = {sid for seq in seqs.values() for _, sid in seq}
        stops: dict[str, Stop] = {}
        for s in _rows(z, "stops.txt"):
            if s["stop_id"] in stop_ids:
                stops[s["stop_id"]] = Stop(s["stop_id"], s["stop_name"], float(s["stop_lat"]), float(s["stop_lon"]))
        shape_ids = {t[4] for t in trips.values()}
        shapes: dict[str, list[tuple[int, float, float]]] = defaultdict(list)
        for p in _rows(z, "shapes.txt"):
            if p["shape_id"] in shape_ids:
                shapes[p["shape_id"]].append((int(p["shape_pt_sequence"]), float(p["shape_pt_lat"]), float(p["shape_pt_lon"])))
        feed_end = None
        if "feed_info.txt" in z.namelist():
            for r in _rows(z, "feed_info.txt"):
                feed_end = r.get("feed_end_date") or feed_end

    by_variant: dict[tuple[int, int], list[str]] = defaultdict(list)
    for tid, (rid, var, *_rest) in trips.items():
        by_variant[(rid, var)].append(tid)
    variants: dict[tuple[int, int], GtfsVariant] = {}
    for (rid, var), tids in by_variant.items():
        seq_set, geo_set = set(), set()
        headsigns, directions = Counter(), set()
        for tid in tids:
            _, _, hs, direction, shape_id = trips[tid]
            seq = tuple(sid for _, sid in sorted(seqs.get(tid, [])))
            if seq:
                seq_set.add(seq)
            pts = tuple((round(la, 5), round(lo, 5)) for _, la, lo in sorted(shapes.get(shape_id, [])))
            if pts:
                geo_set.add(pts)
            headsigns[hs] += 1
            directions.add(direction)
        v = GtfsVariant(rid, var, headsign=headsigns.most_common(1)[0][0])
        if len(seq_set) > 1 or len(geo_set) > 1 or len(directions) > 1:
            v.status = "ambiguous"
            v.note = "wariant ma więcej niż jedną sekwencję słupków, geometrię lub kierunek"
        elif seq_set and geo_set:
            seq = next(iter(seq_set))
            v.stops = [stops[s] for s in seq if s in stops]
            v.shape = list(next(iter(geo_set)))
            v.direction = next(iter(directions))
            if len(v.stops) < 2 or len(v.stops) != len(seq):
                v.status = "ambiguous"
                v.note = "niekompletne słupki wariantu"
        else:
            v.status = "ambiguous"
            v.note = "brak słupków lub geometrii"
        variants[(rid, var)] = v
    return Gtfs(dict(route_ids), variants, feed_end, _file_hash(path), path.stat().st_size)
