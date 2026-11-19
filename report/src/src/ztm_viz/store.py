"""Zapis wyników przetwarzania do SQLite i uzupełnienie podsumowania jakości."""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone

from .db import OBS_COLUMNS
from .params import RULES_VERSION, TIMEZONE
from .timeutil import iso_z


def fill(con, archive, gtfs_path, lines, sel, in_range, res, obs, courses, state, gt, params) -> None:
    quality = state["quality"]
    models = state["models"]
    # --- źródła ------------------------------------------------------------------------------
    for s in res.sources:
        c = s.capture
        con.execute("insert into sources values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (s.id, c.snapshot_key, c.manifest_key, c.run_status, c.source_status, c.url, c.slot, c.fetched_at,
                     c.received_at, c.stored_at, int(c.provenance_gap), s.read_error, s.records))
    # --- kursy i fragmenty ---------------------------------------------------------------------
    obs_info: dict[int, tuple] = {}
    for c in courses:
        first_obs = c.fragments[0].obs[0]
        t0 = min(f.t0 for f in c.fragments)
        t1 = max(f.t1 for f in c.fragments)
        gv = gt.variants.get(c.fragments[0].variant)
        con.execute("insert into courses values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (c.id, c.line, c.service, c.sched_start, c.dir, c.variant_key, c.variant_status,
                     first_obs.headsign, first_obs.vehicle_code, t0, t1, c.n_obs, c.truncated))
        for f in c.fragments:
            con.execute("insert into fragments values(?,?,?,?,?,?,?,?,?,?,?)",
                        (f.id, c.id, f.vehicle_id, f.variant[0], f.variant[1], f.t0, f.t1, len(f.obs), f.status,
                         f.match_fraction, f.note))
            out = state["outcomes"].get(f.id)
            lm = models[c.line]
            for seq, o in enumerate(f.obs):
                flags, s, d, gid, phase = [], None, None, None, None
                if out is not None:
                    m = out.matches[seq]
                    phase = out.phases[seq]
                    if m is None:
                        flags.append("unmatched")
                    else:
                        s, d = m.s, m.dist
                        if m.ambiguous:
                            flags.append("ambiguous")
                        else:
                            idx = lm.routes[f.variant].segment_index(m.s)
                            gid = lm.seg_map[f.variant][idx] if idx is not None else None
                if o.delay is None:
                    flags.append("no_delay")
                obs_info[o.id] = (c.id, f.id, seq, s, d, gid, phase, json.dumps(flags))
    for o in obs:
        info = obs_info.get(o.id, (None, None, None, None, None, None, None, "[]"))
        row = (o.id, o.line, o.vehicle_id, o.t, o.route_id, o.trip_id, o.headsign, o.vehicle_code, o.vehicle_service,
               o.sched_start, o.lat, o.lon, o.delay, o.speed, o.direction, o.gps_quality, o.status, o.reason, o.raw_count,
               *info)
        con.execute(f"insert into observations({','.join(OBS_COLUMNS)}) values({','.join('?' * len(OBS_COLUMNS))})", row)
        con.executemany("insert into obs_sources values(?,?)", [(o.id, sid) for sid in o.sources])
    # --- odcinki, warianty, wartości ------------------------------------------------------------
    for line, lm in models.items():
        for sg in lm.segments:
            f, t = sg["from"], sg["to"]
            con.execute("insert into segments values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                        (line, sg["id"], sg["dir"], f.stop_id, f.name, f.lat, f.lon, t.stop_id, t.name, t.lat, t.lon,
                         sg["length_m"], json.dumps([[round(a, 6), round(b, 6)] for a, b in sg["path"]])))
    var_stats: dict[tuple, dict] = {}
    for c in courses:
        for f in c.fragments:
            d = var_stats.setdefault((c.line, f.variant), {"courses": set(), "obs": 0, "status": Counter(), "heads": Counter()})
            d["heads"].update(o.headsign for o in f.obs if o.headsign)
            d["courses"].add(c.id)
            d["obs"] += len(f.obs)
            d["status"][f.status] += 1
    for (line, (rid, tid)), d in sorted(var_stats.items(), key=lambda kv: (kv[0][0], str(kv[0][1]))):
        gv = gt.variants.get((rid, tid)) if rid is not None else None
        status = "absent_in_gtfs" if gv is None else gv.status
        segs = models[line].seg_map.get((rid, tid), [])
        con.execute("insert into variants values(?,?,?,?,?,?,?,?,?,?,?)",
                    (line, f"{rid}-{tid}", rid, tid, gv.direction if gv is not None and status == "ok" else None,
                     gv.headsign if gv is not None else (d["heads"].most_common(1)[0][0] if d["heads"] else None), status, gv.note if gv is not None else None,
                     len(d["courses"]), d["obs"], json.dumps(segs)))
    for cid, fid, line, gid, v, f in state["values"]:
        so = f.obs
        con.execute("insert into segment_values values(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (cid, fid, line, gid, so[v.end_i].id, so[v.end_i].t, v.end_delay, v.dist, v.gap,
                     so[v.start_i].id if v.start_i is not None else None,
                     so[v.start_i].t if v.start_i is not None else None, v.start_delay, v.start_kind))
    for cid, fid, line, gid, p in state["passes"]:
        con.execute("insert into segment_passes values(?,?,?,?,?,?,?)",
                    (cid, fid, line, gid, int(p.has_value), int(p.has_change), p.note))
    for cid, (frag, a) in state["arrivals"].items():
        con.execute("insert into course_arrival values(?,?,?,?)",
                    (cid, frag.obs[a.i].id if a.i is not None else None, a.delay, a.uncertain))
    # --- podsumowanie jakości, metadane -------------------------------------------------------------
    quality["format"] = 1
    quality["range"] = {"from": sel.days[0].isoformat(), "to": sel.days[-1].isoformat(),
                        "days": [d.isoformat() for d in sel.days], "skipped_days": sel.skipped, "timezone": TIMEZONE}
    quality["inputs"] = {"archive": str(archive), "gtfs": str(gtfs_path), "gtfs_sha256": gt.sha256,
                         "gtfs_size": gt.size, "gtfs_feed_end_date": gt.feed_end_date,
                         "first_slot": iso_z(in_range[0].slot), "last_slot": iso_z(in_range[-1].slot),
                         "attempts_in_range": len(in_range)}
    quality["counts"] = {
        "source_records": len(res.sources), "snapshots_read": sum(1 for s in res.sources if s.read_error is None),
        "snapshot_errors": res.snapshot_errors, "bad_records": res.bad_records, "source_errors": res.source_errors,
        "provenance_gaps": sum(1 for s in res.sources if s.capture.provenance_gap and s.capture.snapshot_exists),
        "raw_records": sum(s.records for s in res.sources), "observations": len(obs),
        "conflicts": sum(1 for o in obs if o.status == "conflict"),
        "without_trip": sum(1 for o in obs if o.status == "ok" and not o.assigned),
        "partial_runs": sum(1 for s in res.sources if s.capture.run_status == "partial"),
    }
    empty = [ln for ln in lines if not any(c.line == ln for c in courses)]
    quality["lines_without_data"] = empty
    quality["notes"] = ([f"Brak danych (kursów) dla linii: {', '.join(empty)}."] if empty else []) + [
        "Wartości opóźnień pochodzą z archiwalnego GPS; rozkład GTFS służy wyłącznie jako pomocnicza geometria i nazwy.",
        "Konflikty wersji tej samej obserwacji są oceniane tylko wśród rekordów wskazanych linii.",
    ]
    meta = {"rules_version": RULES_VERSION, "lines": json.dumps(lines), "range": json.dumps(quality["range"]),
            "params": json.dumps(params.as_dict()), "inputs": json.dumps(quality["inputs"]),
            "created": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    con.executemany("insert into meta values(?,?)", list(meta.items()))
    con.execute("insert into diagnostics values('quality', ?)", (json.dumps(quality, ensure_ascii=False),))
