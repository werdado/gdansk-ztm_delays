"""Polecenie `prepare`: archiwum + GTFS -> SQLite (obserwacje, kursy, odcinki, wartości) i podsumowanie jakości."""
from __future__ import annotations

import json
import os
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import numpy as np

from . import archive as arch
from . import courses as crs
from . import db, gtfs as gtfs_mod, store
from .ingest import ingest
from .matching import match_fragment
from .params import Params
from .route import Route, project
from .values import PObs, analyze


@dataclass
class FragmentOutcome:
    passes: dict
    values: dict
    arrival: object
    phases: list[str]
    matches: list


@dataclass
class LineModel:
    routes: dict[tuple[int, int], Route] = field(default_factory=dict)
    seg_map: dict[tuple[int, int], list[int]] = field(default_factory=dict)
    segments: list[dict] = field(default_factory=list)


def _path_compatible(a: list[tuple[float, float]], b: list[tuple[float, float]], tol: float) -> bool:
    def sample(path):
        xs, ys = project([p[1] for p in path], [p[0] for p in path])
        pts = np.column_stack([xs, ys])
        seg = np.hypot(*(pts[1:] - pts[:-1]).T)
        cum = np.concatenate([[0], np.cumsum(seg)])
        if cum[-1] == 0:
            return np.repeat(pts[:1], 5, axis=0)
        t = np.linspace(0, cum[-1], 5)
        return np.column_stack([np.interp(t, cum, pts[:, 0]), np.interp(t, cum, pts[:, 1])])
    d = np.hypot(*(sample(a) - sample(b)).T)
    return bool(d.max() <= tol)


def _build_line_model(gt: gtfs_mod.Gtfs, variant_keys: list[tuple[int, int]], params: Params) -> LineModel:
    lm = LineModel()
    clusters: dict[tuple, list[int]] = defaultdict(list)       # (dir, from, to) -> seg ids
    for key in sorted(variant_keys):
        v = gt.variants.get(key)
        if v is None or v.status != "ok":
            continue
        route = Route.build(v, params)
        lm.routes[key] = route
        ids = []
        for j in range(route.n_segments):
            a, b = route.stop_chain[j], route.stop_chain[j + 1]
            path = route.subpath_latlon(a, b)
            ck = (v.direction, v.stops[j].stop_id, v.stops[j + 1].stop_id)
            found = None
            for sid in clusters[ck]:
                if _path_compatible(lm.segments[sid]["path"], path, params.merge_path_tol_m):
                    found = sid
                    break
            if found is None:
                found = len(lm.segments)
                clusters[ck].append(found)
                f, t = v.stops[j], v.stops[j + 1]
                lm.segments.append({"id": found, "dir": v.direction, "from": f, "to": t,
                                    "length_m": b - a, "path": path})
            ids.append(found)
        lm.seg_map[key] = ids
    return lm


def _fragment_pobs(f: crs.Fragment):
    lons = [o.lon if o.lon is not None else np.nan for o in f.obs]
    lats = [o.lat if o.lat is not None else np.nan for o in f.obs]
    x, y = project(lons, lats)
    return [PObs(o.t, o.delay, o.speed, float(xx), float(yy)) for o, xx, yy in zip(f.obs, x, y)], list(zip(x, y))


def prepare(archive: Path, gtfs_path: Path, out: Path, lines: list[str], date_from: date | None = None,
            date_to: date | None = None, params: Params | None = None) -> None:
    params = params or Params()
    archive, gtfs_path, out = Path(archive), Path(gtfs_path), Path(out)
    if not (archive / "runs").is_dir() and not (archive / "snapshots").is_dir():
        raise SystemExit(f"Niepoprawne wejście: {archive} nie wygląda na archiwum (brak runs/ i snapshots/).")
    if not gtfs_path.is_file():
        raise SystemExit(f"Niepoprawne wejście: brak pliku GTFS {gtfs_path}.")
    caps = arch.scan(archive)
    sel = arch.select_days(caps, params, date_from, date_to)
    in_range = [c for c in caps if sel.start_utc <= c.slot < sel.end_utc]
    line_set = set(lines)
    gt = gtfs_mod.load(gtfs_path, line_set)
    res = ingest(archive, in_range, line_set, sel.start_utc, sel.end_utc)
    obs = res.observations
    if not any(o.status == "ok" and o.assigned for o in obs):
        raise SystemExit("Brak użytecznych danych: w wybranym zakresie nie ma obserwacji z przypisaniem do kursu dla wskazanych linii.")

    courses = crs.build(obs, params, sel.start_utc, sel.end_utc)
    state = _process(courses, obs, gt, lines, params)
    _write(out, archive, gtfs_path, lines, sel, in_range, res, obs, courses, state, gt, params)


def _process(courses, obs, gt, lines, params):
    by_line_variants: dict[str, set] = defaultdict(set)
    for c in courses:
        for f in c.fragments:
            by_line_variants[c.line].add(f.variant)
    models = {line: _build_line_model(gt, [k for k in by_line_variants[line] if k[0] is not None], params) for line in lines}
    state = {"models": models, "outcomes": {}, "passes": [], "values": [], "arrivals": {}, "speed": defaultdict(lambda: {"with": [], "without": []})}
    # fragmenty równoległe wyłączone w crs.build; reszta analizowana
    fid = 0
    for c in courses:
        lm = models[c.line]
        for f in c.fragments:
            fid += 1
            f.id = fid
            if f.status != "ok":
                continue
            rid, tid = f.variant
            gv = gt.variants.get((rid, tid)) if rid is not None else None
            if gv is None:
                f.status, f.note = "absent_in_gtfs", "wariant nieobecny w rozkładzie pomocniczym"
                continue
            if gv.status != "ok":
                f.status, f.note = "ambiguous", gv.note
                continue
            route = lm.routes[(rid, tid)]
            pobs, xy = _fragment_pobs(f)
            matches = match_fragment(route, [(x, y, o.t) for (x, y), o in zip(xy, f.obs)], params)
            matched = sum(1 for m in matches if m is not None)
            f.match_fraction = matched / len(matches)
            if f.match_fraction < params.min_match_fraction:
                f.status, f.note = "variant_mismatch", "przebieg obserwacji niezgodny z wariantem pomocniczym"
                continue
            r = analyze(route, pobs, matches, params)
            state["outcomes"][f.id] = FragmentOutcome(r.passes, r.values, r.arrival, r.phases, matches)
    for c in courses:
        _finish_course(c, gt, state, models[c.line])
    state["quality"] = _quality(courses, obs, lines, state, gt, params)
    return state


def _finish_course(c, gt, state, lm):
    ok = [f for f in c.fragments if f.status == "ok"]
    first = ok[0] if ok else (c.fragments[0] if c.fragments else None)
    rid, tid = first.variant
    c.variant_key = f"{rid}-{tid}"
    c.variant_status = "ok" if ok else first.status
    gv = gt.variants.get((rid, tid))
    c.dir = gv.direction if gv is not None and gv.status == "ok" else None
    chosen: dict[int, tuple] = {}       # odcinek -> (fragment, indeks, przejazd, wartość); kurs wnosi najwyżej jedną wartość
    for f in ok:
        out = state["outcomes"][f.id]
        ids = lm.seg_map[f.variant]
        for seg_idx, p in sorted(out.passes.items()):
            gid = ids[seg_idx]
            v = out.values.get(seg_idx)
            if gid not in chosen or (v is not None and chosen[gid][3] is None):
                chosen[gid] = (f, seg_idx, p, v)    # wartość wygrywa z samą notatką o braku
    for gid, (f, seg_idx, p, v) in sorted(chosen.items()):
        out = state["outcomes"][f.id]
        route = lm.routes[f.variant]
        state["passes"].append((c.id, f.id, c.line, gid, p))
        if v is not None:
            state["values"].append((c.id, f.id, c.line, gid, v, f))
        sp = [o.speed for o, m in zip(f.obs, out.matches) if m is not None and not m.ambiguous
              and route.segment_index(m.s) == seg_idx and o.speed is not None]
        if sp:
            state["speed"][(c.line, gid)]["with" if v is not None else "without"].append(sum(sp) / len(sp))
    for f in ok:
        out = state["outcomes"][f.id]
        if out.arrival is not None:
            prev = state["arrivals"].get(c.id)
            if prev is None or (prev[1].delay is None and out.arrival.delay is not None):
                state["arrivals"][c.id] = (f, out.arrival)


def _pct(vals, q):
    if not vals:
        return None
    vals = sorted(vals)
    return round(vals[min(len(vals) - 1, int(q * len(vals)))], 1)


def _quality(courses, obs, lines, state, gt, params):
    q: dict = {"lines": {}}
    per_line_obs = defaultdict(list)
    for o in obs:
        per_line_obs[o.line].append(o)
    for line in lines:
        lo = per_line_obs.get(line, [])
        skipped = [o for o in lo if not (o.status == "ok" and o.assigned) and o.status != "conflict"]
        lc = [c for c in courses if c.line == line]
        absent: dict[str, dict] = {}
        for c in lc:
            for f in c.fragments:
                if f.status == "absent_in_gtfs":
                    key = f"{f.variant[0]}-{f.variant[1]}"
                    d = absent.setdefault(key, {"variant": key, "route_id": f.variant[0], "trip_id": f.variant[1], "courses": 0, "observations": 0, "_c": set()})
                    d["observations"] += len(f.obs)
                    d["_c"].add(c.id)
        for d in absent.values():
            d["courses"] = len(d.pop("_c"))
        cov: dict[int, dict] = {}
        dist_by_seg: dict[int, list] = defaultdict(list)
        for cid, fid, ln, gid, p in state["passes"]:
            if ln != line:
                continue
            d = cov.setdefault(gid, {"passes": 0, "with_value": 0, "with_change": 0})
            d["passes"] += 1
            d["with_value"] += p.has_value
            d["with_change"] += p.has_change
        for cid, fid, ln, gid, v, f in state["values"]:
            if ln == line:
                dist_by_seg[gid].append(v.dist)
        for gid, d in cov.items():
            ds = dist_by_seg.get(gid, [])
            d["dist_p10_p50_p90_m"] = [_pct(ds, .1), _pct(ds, .5), _pct(ds, .9)]
            sp = state["speed"].get((line, gid))
            if sp:
                d["mean_speed_kmh_with_value"] = round(statistics.fmean(sp["with"]), 1) if sp["with"] else None
                d["mean_speed_kmh_without_value"] = round(statistics.fmean(sp["without"]), 1) if sp["without"] else None
        statuses = Counter(f.status for c in lc for f in c.fragments)
        q["lines"][line] = {
            "raw_records": sum(o.raw_count for o in lo),
            "observations": len(lo),
            "conflicts": sum(1 for o in lo if o.status == "conflict"),
            "skipped_records": len(skipped),
            "raw_skipped_records": sum(o.raw_count for o in skipped),
            "courses": len(lc),
            "fragment_status": dict(statuses),
            "variants_absent_in_gtfs": sorted(absent.values(), key=lambda d: d["variant"]),
            "segment_coverage": {str(k): v for k, v in sorted(cov.items())},
        }
    return q


def _write(out, archive, gtfs_path, lines, sel, in_range, res, obs, courses, state, gt, params):
    quality = state["quality"]
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_name(out.name + f".tmp{os.getpid()}")
    qtmp = out.with_name(out.stem + ".quality.json" + f".tmp{os.getpid()}")
    for p in (tmp, qtmp):
        p.unlink(missing_ok=True)
    try:
        con = db.create(str(tmp))
        store.fill(con, archive, gtfs_path, lines, sel, in_range, res, obs, courses, state, gt, params)
        con.commit()
        con.close()
        qtmp.write_text(json.dumps(quality, ensure_ascii=False, indent=1))
        os.replace(tmp, out)
        os.replace(qtmp, out.with_suffix(".quality.json"))
    finally:
        for p in (tmp, qtmp):
            p.unlink(missing_ok=True)
