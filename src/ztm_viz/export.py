"""Polecenie `report`: SQLite -> statyczny katalog raportu (HTML, zasoby, geometria, wkłady i szczegóły kursów)."""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from importlib import resources
from pathlib import Path
from urllib.parse import quote

from .params import RULES_VERSION
from .timeutil import to_local_wall

FORMAT = 1
log = logging.getLogger("ztm_viz")


def _s(v):
    return None if v is None else str(v)


def _dump(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def report(dataset: Path, out: Path) -> None:
    dataset, out = Path(dataset), Path(out)
    if not dataset.is_file():
        raise SystemExit(f"Niepoprawne wejście: brak zbioru {dataset}. Uruchom najpierw `prepare`.")
    web = resources.files("ztm_viz") / "web"
    if not (web / "index.html").is_file():
        raise SystemExit("Brak zasobów przeglądarkowych (ztm_viz/web/index.html).")
    con = sqlite3.connect(f"file:{dataset}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    log.info("report: %s -> %s", dataset, out)
    _check_target(out, dataset)
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.parent / f".{out.name}.tmp{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    try:
        shutil.copytree(str(web), tmp, ignore=shutil.ignore_patterns("__pycache__"))
        _write_data(con, tmp)
        old = None
        if out.exists():
            old = out.parent / f".{out.name}.old{os.getpid()}"
            shutil.rmtree(old, ignore_errors=True)
            os.rename(out, old)
        try:
            os.rename(tmp, out)
        except OSError:
            if old is not None:
                os.rename(old, out)
            raise
        if old is not None:
            shutil.rmtree(old, ignore_errors=True)
        log.info("gotowe: %s", out)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        con.close()


def _check_target(out: Path, dataset: Path) -> None:
    """Nie nadpisujemy katalogu, który nie jest poprzednim raportem (np. z zasobem `dataset.sqlite` albo archiwum)."""
    if not out.exists():
        return
    if not out.is_dir():
        raise SystemExit(f"Niepoprawne wyjście: {out} nie jest katalogiem.")
    resolved = out.resolve()
    if resolved == dataset.resolve().parent or dataset.resolve().is_relative_to(resolved) \
            or (resolved / "runs").exists() or (resolved / "snapshots").exists():
        raise SystemExit(f"Niepoprawne wyjście: {out} zawiera zbiór lub archiwum; wskaż osobny katalog raportu.")
    if any(out.iterdir()) and not ((out / "index.html").is_file() and (out / "data" / "manifest.json").is_file()):
        raise SystemExit(f"Niepoprawne wyjście: {out} nie jest pusty i nie wygląda na poprzedni raport.")


def _write_data(con: sqlite3.Connection, root: Path) -> None:
    meta = dict(con.execute("select key, value from meta").fetchall())
    quality = json.loads(con.execute("select json from diagnostics where key='quality'").fetchone()[0])
    lines = json.loads(meta["lines"])
    rng = json.loads(meta["range"])
    manifest = {"format": FORMAT, "generated": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "rules_version": meta.get("rules_version", RULES_VERSION),
                "range": {"from": rng["from"], "to": rng["to"], "days": rng["days"],
                          "skipped_days": [d["date"] for d in rng["skipped_days"]]},
                "params": json.loads(meta["params"]), "lines": [], "quality": "data/quality.json"}
    for line in lines:
        log.info("  linia %s: geometria, wkłady dób i szczegóły kursów", line)
        entry = _write_line(con, root, line, rng["days"], quality)
        if entry is None:
            continue
        if entry["directions"]:
            manifest["lines"].append(entry)
        else:   # linia bez żadnego wariantu z geometrią pomocniczą: nie ma czego pokazać na mapie ani wykresie
            manifest.setdefault("lines_without_timetable", []).append(
                {"name": line, "courses": entry["courses"], "variants": entry["variants_outside_timetable"]})
    if not manifest["lines"]:
        raise SystemExit("Żadna ze wskazanych linii nie ma wariantów z geometrią pomocniczą – raport byłby pusty.")
    _dump(root / "data" / "quality.json", quality)
    _dump(root / "data" / "manifest.json", manifest)


def _write_line(con, root: Path, line: str, days: list[str], quality: dict):
    n_courses = con.execute("select count(*) from courses where line=?", (line,)).fetchone()[0]
    if n_courses == 0:
        return None
    slug = quote(line, safe="")
    base = f"data/lines/{slug}"
    variants = [dict(r) for r in con.execute("select * from variants where line=? order by key", (line,))]
    segments = [dict(r) for r in con.execute("select * from segments where line=? order by id", (line,))]
    # ---- kierunki i etykiety ------------------------------------------------------------------
    by_dir: dict[int, list[dict]] = defaultdict(list)
    outside = []
    for v in variants:
        if v["status"] == "ok" and v["dir"] is not None:
            by_dir[v["dir"]].append(v)
        else:
            outside.append({"key": v["key"], "route_id": v["route_id"], "trip_id": v["trip_id"], "headsign": v["headsign"] or "",
                            "status": v["status"], "courses": v["courses"], "observations": v["observations"]})
    directions = []
    for d in sorted(by_dir):
        vs = by_dir[d]
        best = max(vs, key=lambda v: v["observations"])
        label = best["headsign"] or "?"
        others = sorted({v["headsign"] for v in vs if v["headsign"] and v["headsign"] != label})
        directions.append({"id": d, "label": label, "other_headsigns": others, "variants": [
            {"key": v["key"], "route_id": v["route_id"], "trip_id": v["trip_id"], "headsign": v["headsign"] or "",
             "in_gtfs": True, "status": v["status"], "courses": v["courses"], "observations": v["observations"]} for v in vs]})
    # ---- geometria -------------------------------------------------------------------------------
    geo_segments = [{"id": s["id"], "dir": s["dir"],
                     "from": {"stop_id": s["from_stop"], "name": s["from_name"], "lat": s["from_lat"], "lon": s["from_lon"]},
                     "to": {"stop_id": s["to_stop"], "name": s["to_name"], "lat": s["to_lat"], "lon": s["to_lon"]},
                     "length_m": round(s["length_m"], 1), "path": json.loads(s["path"])} for s in segments]
    seg_lists = {v["key"]: json.loads(v["segments"]) for v in variants}
    geo_variants = [{"key": v["key"], "dir": v["dir"], "headsign": v["headsign"] or "", "segments": seg_lists[v["key"]]}
                    for v in variants if v["status"] == "ok"]
    _dump(root / base / "geometry.json", {"format": FORMAT, "segments": geo_segments, "variants": geo_variants})
    # ---- wkłady po dobach ---------------------------------------------------------------------
    rows = con.execute("""select sv.*, c.dir, c.variant_key, c.sched_start, c.vehicle_code, c.vehicle_service
                          from segment_values sv join courses c on c.id=sv.course_id
                          where sv.line=? order by sv.end_t, sv.course_id, sv.seg_id""", (line,)).fetchall()
    per_day: dict[str, dict] = {d: {"courses": [], "idx": {}, "c": {k: [] for k in
                                    ("course", "seg", "endL", "end", "startL", "start", "dist")}} for d in days}
    for r in rows:
        endL = to_local_wall(r["end_t"])
        day = datetime.fromtimestamp(endL, timezone.utc).strftime("%Y-%m-%d")
        b = per_day.get(day)
        if b is None:
            continue
        if r["course_id"] not in b["idx"]:
            b["idx"][r["course_id"]] = len(b["courses"])
            b["courses"].append({"id": r["course_id"], "dir": r["dir"], "variant": r["variant_key"],
                                 "startL": to_local_wall(r["sched_start"]), "vehicle": r["vehicle_code"],
                                 "service": r["vehicle_service"]})
        c = b["c"]
        c["course"].append(b["idx"][r["course_id"]])
        c["seg"].append(r["seg_id"])
        c["endL"].append(endL)
        c["end"].append(r["end_delay"])
        c["startL"].append(to_local_wall(r["start_t"]) if r["start_delay"] is not None else None)
        c["start"].append(r["start_delay"])
        c["dist"].append(round(r["end_dist"], 1) if r["end_dist"] is not None else None)
    day_files = {}
    for d, b in per_day.items():
        path = f"{base}/days/{d}.json"
        _dump(root / path, {"format": FORMAT, "line": line, "date": d, "courses": b["courses"], "c": b["c"]})
        day_files[d] = path
    # ---- szczegóły kursów ----------------------------------------------------------------------
    sources = {r["id"]: dict(r) for r in con.execute("select * from sources")}
    for crow in con.execute("select * from courses where line=? order by id", (line,)):
        _write_course(con, root / base / "courses", crow, sources, seg_lists.get(crow["variant_key"], []))
    skipped = quality["lines"].get(line, {}).get("skipped_records", 0)
    return {"name": line, "slug": slug, "skipped_records": skipped,
            "raw_skipped_records": quality["lines"].get(line, {}).get("raw_skipped_records", 0), "courses": n_courses,
            "directions": directions, "variants_outside_timetable": outside, "geometry": f"{base}/geometry.json", "days": day_files}


def _write_course(con, dirpath: Path, c, sources: dict, variant_segs: list[int]) -> None:
    cid = c["id"]
    obs = con.execute("select o.*, f.status as fstatus from observations o left join fragments f on f.id=o.fragment_id "
                      "where o.course_id=? order by o.t_utc, o.vehicle_id", (cid,)).fetchall()
    idx = {o["id"]: i for i, o in enumerate(obs)}
    src_index: dict[int, int] = {}
    src_list = []
    obs_out = []
    for o in obs:
        sidx = []
        for (sid,) in con.execute("select source_id from obs_sources where obs_id=? order by source_id", (o["id"],)):
            if sid not in src_index:
                s = sources[sid]
                src_index[sid] = len(src_list)
                src_list.append({"snapshot": s["snapshot_key"], "manifest": s["manifest_key"], "run_status": s["run_status"],
                                 "source_status": s["source_status"], "url": s["url"], "fetchedAt": s["fetched_at"],
                                 "receivedAt": s["received_at"], "storedAt": s["stored_at"],
                                 "provenance_gap": bool(s["provenance_gap"])})
            sidx.append(src_index[sid])
        flags = json.loads(o["flags"] or "[]")
        if o["fstatus"] not in (None, "ok"):
            flags.append(o["fstatus"])
        obs_out.append({"tL": to_local_wall(o["t_utc"]), "tU": o["t_utc"], "delay": o["delay"], "speed": o["speed"],
                        "lat": round(o["lat"], 6) if o["lat"] is not None else None,
                        "lon": round(o["lon"], 6) if o["lon"] is not None else None,
                        "s": round(o["s"], 1) if o["s"] is not None else None, "seg": o["seg_id"],
                        "phase": o["phase"] or "unknown", "flags": flags, "src": sidx, "vehicle": _s(o["vehicle_code"])})
    order = {sid: i for i, sid in enumerate(variant_segs)}
    passes = con.execute("""select sp.seg_id, sp.note, sv.* from segment_passes sp
                            left join segment_values sv on sv.course_id=sp.course_id and sv.seg_id=sp.seg_id and sv.fragment_id=sp.fragment_id
                            where sp.course_id=?""", (cid,)).fetchall()
    segs = []
    for p in sorted(passes, key=lambda r: (order.get(r["seg_id"], 1 << 30), r["seg_id"])):
        entry = {"seg": p["seg_id"], "end": None, "start": None, "change": None, "note": p["note"]}
        if p["end_obs"] is not None:
            entry["end"] = {"obs": idx[p["end_obs"]], "delay": p["end_delay"],
                            "dist_m": round(p["end_dist"], 1) if p["end_dist"] is not None else None, "gap_s": p["end_gap"]}
            if p["start_delay"] is not None:
                entry["start"] = {"obs": idx[p["start_obs"]], "delay": p["start_delay"], "kind": p["start_kind"]}
                entry["change"] = p["end_delay"] - p["start_delay"]
        segs.append(entry)
    arr = con.execute("select * from course_arrival where course_id=?", (cid,)).fetchone()
    arrival = None
    if c["variant_status"] == "ok" and arr is not None:
        arrival = {"obs": idx.get(arr["obs_id"]) if arr["obs_id"] is not None else None, "delay": arr["delay"],
                   "uncertain": arr["uncertain"]}
    detail = {"format": FORMAT, "id": cid, "line": c["line"], "dir": c["dir"], "variant": c["variant_key"],
              "headsign": c["headsign"] or "", "vehicle": _s(c["vehicle_code"]), "service": c["vehicle_service"],
              "startL": to_local_wall(c["sched_start"]), "truncated": c["truncated"], "variant_status": c["variant_status"],
              "segments": segs, "arrival": arrival, "observations": obs_out, "sources": src_list}
    _dump(dirpath / f"{cid}.json", detail)
