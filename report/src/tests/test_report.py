"""Eksport raportu: statyczny katalog, kontrakt danych i niezależność od surowego archiwum."""
import json
import shutil
from pathlib import Path

import pytest

from ztm_viz.cli import main
from helpers import prepare
from world import STANDARD_STEPS, run_scenario, utc

BASE = utc("2026-11-10T10:00:00Z")


@pytest.fixture
def report(world):
    b, gtfs, out = world
    b.add("2026-11-10T12:00:00Z", [rec for _, rec in run_scenario(BASE, STANDARD_STEPS)])
    b.add("2026-11-10T12:00:20Z", [rec for _, rec in run_scenario(BASE, STANDARD_STEPS)[:3]])   # powtórzenie zapisu
    prepare(b.root, gtfs, out, ["7"])
    dest = out.parent / "report"
    shutil.rmtree(b.root)                      # raport powstaje wyłącznie z SQLite
    main(["report", "--dataset", str(out), "--out", str(dest)])
    return dest


def load(p: Path):
    return json.loads(p.read_text())


def test_report_is_static_directory_with_relative_manifest_paths(report):
    assert (report / "index.html").is_file()
    m = load(report / "data" / "manifest.json")
    assert m["range"]["from"] == "2026-11-04" and m["range"]["to"] == "2026-11-10"
    line = m["lines"][0]
    assert line["name"] == "7" and not line["geometry"].startswith("/")
    for path in [line["geometry"], *line["days"].values(), m["quality"]]:
        assert (report / path).is_file() and ".." not in path


def test_line_list_comes_from_dataset_only(world):
    b, gtfs, out = world
    b.add("2026-11-10T12:00:00Z", [rec for _, rec in run_scenario(BASE, STANDARD_STEPS, line="N8", route_id=8, trip=6,
                                                                  lat=54.36, service="008-01", vehicle_id=3)])
    prepare(b.root, gtfs, out, ["N8"])
    main(["report", "--dataset", str(out), "--out", str(out.parent / "r")])
    m = load(out.parent / "r" / "data" / "manifest.json")
    assert [l["name"] for l in m["lines"]] == ["N8"]
    assert m["lines"][0]["directions"][0]["label"] == "Nocna"


def test_day_bundle_holds_exact_contributions_once_per_course(report):
    m = load(report / "data" / "manifest.json")
    day = load(report / m["lines"][0]["days"]["2026-11-10"])
    c = day["c"]
    assert len(day["courses"]) == 1
    by_seg = {}
    for i in range(len(c["seg"])):
        by_seg.setdefault(c["seg"][i], []).append((c["end"][i], c["start"][i]))
    assert sorted(v[0] for v in by_seg.values()) == [(140, 120), (160, 140), (180, 160), (215, 180)]
    assert all(len(v) == 1 for v in by_seg.values())     # powielone zapisy nie dublują wkładu
    # czas lokalny: 10:00 UTC to 11:00 czasu lokalnego (CET)
    assert (day["courses"][0]["startL"] % 86400) == 11 * 3600


def test_course_detail_traces_values_to_source_records(report):
    m = load(report / "data" / "manifest.json")
    cid = load(report / m["lines"][0]["days"]["2026-11-10"])["courses"][0]["id"]
    d = load(report / "data" / "lines" / "7" / "courses" / f"{cid}.json")
    assert d["variant_status"] == "ok" and d["arrival"]["delay"] == 215
    first = d["observations"][0]
    assert first["phase"] == "pre_departure"
    assert d["observations"][-1]["phase"] == "terminal_after_arrival"
    assert d["observations"][1]["src"] and all(
        d["sources"][i]["snapshot"].startswith("snapshots/gps/") and d["sources"][i]["manifest"].startswith("runs/")
        for i in d["observations"][1]["src"])
    # powtórzony zapis: obserwacja pochodzi z dwóch zapisów źródłowych
    assert len(d["observations"][0]["src"]) == 2
    seg = d["segments"][0]
    assert seg["end"]["delay"] == 140 and seg["start"]["delay"] == 120 and seg["change"] == 20
    assert d["observations"][seg["end"]["obs"]]["delay"] == 140


def test_report_replaces_previous_directory_only_after_complete_write(world, monkeypatch):
    b, gtfs, out = world
    b.add("2026-11-10T12:00:00Z", [rec for _, rec in run_scenario(BASE, STANDARD_STEPS)])
    prepare(b.root, gtfs, out, ["7"])
    dest = out.parent / "report"
    main(["report", "--dataset", str(out), "--out", str(dest)])
    marker = dest / "marker.txt"
    marker.write_text("stare")
    import ztm_viz.export as ex
    monkeypatch.setattr(ex, "_write_data", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("przerwano")))
    with pytest.raises(RuntimeError):
        main(["report", "--dataset", str(out), "--out", str(dest)])
    assert marker.read_text() == "stare"
    assert not [p for p in dest.parent.iterdir() if p.name.startswith(".report")]


def test_missing_dataset_is_an_error(tmp_path):
    with pytest.raises(SystemExit):
        main(["report", "--dataset", str(tmp_path / "brak.sqlite"), "--out", str(tmp_path / "r")])


def test_report_refuses_to_replace_a_directory_that_is_not_a_report(world):
    b, gtfs, out = world
    b.add("2026-11-10T12:00:00Z", [rec for _, rec in run_scenario(BASE, STANDARD_STEPS)])
    prepare(b.root, gtfs, out, ["7"])
    with pytest.raises(SystemExit):
        main(["report", "--dataset", str(out), "--out", str(out.parent)])      # katalog z dataset.sqlite
    assert out.exists()
    with pytest.raises(SystemExit):
        main(["report", "--dataset", str(out), "--out", str(b.root)])          # archiwum
    assert (b.root / "runs").exists()


def test_line_absent_from_timetable_is_not_offered_but_stays_in_quality(world):
    b, gtfs, out = world
    b.add("2026-11-10T12:00:00Z", [rec for _, rec in run_scenario(BASE, STANDARD_STEPS)]
          + [rec for _, rec in run_scenario(BASE, STANDARD_STEPS, line="171", route_id=10171, service="171-01", vehicle_id=9)])
    prepare(b.root, gtfs, out, ["7", "171"])
    main(["report", "--dataset", str(out), "--out", str(out.parent / "r")])
    m = load(out.parent / "r" / "data" / "manifest.json")
    assert [l["name"] for l in m["lines"]] == ["7"]
    assert m["lines_without_timetable"][0]["name"] == "171"
