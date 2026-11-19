"""Syntetyczny świat testowy: mini-archiwum, mini-GTFS i pomocnicze rekordy GPS."""
from __future__ import annotations

import csv
import gzip
import io
import json
import zipfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

M_PER_DEG_LON = 64770.0  # ok. na szerokości 54,35°
LAT0 = 54.35


def lon_at(meters: float) -> float:
    return 18.5 + meters / M_PER_DEG_LON


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def utc(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def vehicle(t: datetime, meters: float, delay, speed=0, *, line="7", route_id=7, trip=5,
            vehicle_id=100, service="007-01", start="2026-11-10T10:00:00Z", headsign="Koniec",
            lat=LAT0, **extra) -> dict:
    rec = {
        "generated": iso(t), "routeShortName": line, "tripId": trip, "routeId": route_id,
        "headsign": headsign, "vehicleCode": str(vehicle_id), "vehicleService": service,
        "vehicleId": vehicle_id, "speed": speed, "direction": 90, "delay": delay,
        "scheduledTripStartTime": start, "lat": lat, "lon": lon_at(meters), "gpsQuality": 3,
    }
    rec.update(extra)
    return rec


def unassigned(rec: dict) -> dict:
    out = dict(rec)
    out.update(tripId=None, scheduledTripStartTime=None, headsign="")
    return out


class ArchiveBuilder:
    """Zapisuje zapisy GPS i manifesty w układzie kolektora."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.n = 0

    def add(self, slot: str, vehicles: list[dict], *, manifest=True, status="complete",
            corrupt=False, snapshot=True) -> str:
        slot_dt = utc(slot)
        date = slot_dt.strftime("%Y-%m-%d")
        slot_name = slot_dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        self.n += 1
        attempt = f"00000000-0000-4000-8000-{self.n:012d}"
        key = f"snapshots/gps/{date}/{slot_name}/{attempt}.json.gz"
        if snapshot:
            p = self.root / key
            p.parent.mkdir(parents=True, exist_ok=True)
            if corrupt:
                p.write_bytes(b"to nie jest gzip")
            else:
                payload = json.dumps({"lastUpdate": iso(slot_dt), "vehicles": vehicles})
                p.write_bytes(gzip.compress(payload.encode()))
        if manifest:
            m = self.root / "runs" / date / slot_name / f"{attempt}.json"
            m.parent.mkdir(parents=True, exist_ok=True)
            m.write_text(json.dumps({
                "schemaVersion": 1, "attemptId": attempt, "scheduledFor": slot_name, "status": status,
                "sources": [{"source": "gps", "url": "https://example/gps", "status": "stored" if snapshot else "error",
                             "fetchedAt": slot_name, "receivedAt": slot_name, "storedAt": slot_name,
                             **({"key": key} if snapshot else {})}],
            }))
        return key

    def add_boundaries(self):
        """Puste zapisy obejmujące początek i koniec każdej doby lokalnej 4–10 XI oraz niepełne krańce."""
        self.add("2026-11-03T17:14:14Z", [])
        for day in range(4, 11):
            self.add(f"2026-11-{day - 1:02d}T23:00:00Z", [])
            self.add(f"2026-11-{day:02d}T22:59:40Z", [])
        self.add("2026-11-11T07:36:20Z", [])


def write_gtfs(path: Path, *, extra_variant_shapes=False):
    """Linia 7 (route 7, wariant 5), N8 (route 8, wariant 6), 171 (route 171 w GTFS) i linia 9 (bez GTFS)."""
    def csvtext(header, rows):
        b = io.StringIO()
        w = csv.writer(b)
        w.writerow(header)
        w.writerows(rows)
        return b.getvalue()

    def stops_for(prefix, lat):
        return [(f"{prefix}{i}", f"Przystanek {prefix}{i}", lat, lon_at(m)) for i, m in enumerate([0, 500, 1000, 1500, 2000])]

    s7 = stops_for("a", LAT0)
    s8 = stops_for("b", LAT0 + 0.01)
    shapes = []
    for sid, lat in (("sh7", LAT0), ("sh7b", LAT0), ("sh8", LAT0 + 0.01)):
        for i, m in enumerate([0, 1000, 2000]):
            shapes.append((sid, lat, lon_at(m), i))
    if extra_variant_shapes:
        shapes = [r for r in shapes if r[0] != "sh7b"] + [("sh7b", LAT0 + 0.001, lon_at(m), i) for i, m in enumerate([0, 1000, 2000])]
    stop_times = []
    for trip, stops in (("100_5_007-01", s7), ("101_5_007-02", s7), ("200_6_008-01", s8)):
        for seq, st in enumerate(stops, 1):
            stop_times.append((trip, "10:00:00", "10:00:00", st[0], seq))
    files = {
        "routes.txt": csvtext(["route_id", "agency_id", "route_short_name", "route_type"],
                              [(7, 1, "7", 900), (8, 1, "N8", 700), (171, 1, "171", 700)]),
        "trips.txt": csvtext(["route_id", "service_id", "trip_id", "trip_headsign", "direction_id", "shape_id"],
                             [(7, 1, "100_5_007-01", "Koniec", 0, "sh7"), (7, 1, "101_5_007-02", "Koniec", 0, "sh7b"),
                              (8, 1, "200_6_008-01", "Nocna", 1, "sh8")]),
        "stops.txt": csvtext(["stop_id", "stop_name", "stop_lat", "stop_lon"], s7 + s8),
        "stop_times.txt": csvtext(["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"], stop_times),
        "shapes.txt": csvtext(["shape_id", "shape_pt_lat", "shape_pt_lon", "shape_pt_sequence"], shapes),
        "calendar_dates.txt": csvtext(["service_id", "date", "exception_type"], [(1, "20261120", 1)]),
        "feed_info.txt": csvtext(["feed_publisher_name", "feed_end_date"], [("ZTM", "20261125")]),
    }
    with zipfile.ZipFile(path, "w") as z:
        for name, text in files.items():
            z.writestr(name, text)


def run_scenario(base: datetime, steps, **kw):
    """steps: (offset_s, meters, delay, speed) -> lista rekordów z czasem."""
    return [(base + timedelta(seconds=o), vehicle(base + timedelta(seconds=o), m, d, sp, **kw)) for o, m, d, sp in steps]


# Przebieg wzorcowy: przystanki co 500 m (0, 500, ..., 2000), granice 475, 975, 1475, 1975.
STANDARD_STEPS = [
    (0, 5, 100, 0), (20, 10, 110, 0),        # postój przed odjazdem
    (40, 60, 120, 10),                        # początek kursu
    (60, 260, 130, 10), (80, 460, 140, 10),   # koniec odcinka 0: 140 (40 m przed przystankiem)
    (100, 660, 150, 10), (120, 860, 160, 10),  # koniec odcinka 1: 160
    (140, 1060, 170, 10), (160, 1260, 180, 10),  # koniec odcinka 2: 180
    (180, 1480, 190, 10), (200, 1700, 200, 10), (220, 1900, 210, 10),  # dojazd
    (240, 1985, 215, 2),                      # ostatnia obserwacja w ruchu = wartość dojazdu (15 m od słupka)
    (260, 1990, 0, 0), (280, 1991, 0, 0), (300, 1990, 0, 0),  # krańcowy postój, ruchome zero
]
