from datetime import timedelta

import pytest

from helpers import prepare, quality, rows
from world import unassigned, utc, vehicle

T0 = utc("2026-11-10T10:00:00Z")


def test_lines_parameter_is_required(world, capsys):
    b, gtfs, out = world
    with pytest.raises(SystemExit) as e:
        from ztm_viz.cli import main
        main(["prepare", "--archive", str(b.root), "--gtfs", str(gtfs), "--out", str(out)])
    assert e.value.code != 0


def test_only_full_local_days_are_processed(world):
    b, gtfs, out = world
    b.add("2026-11-10T10:00:00Z", [vehicle(T0, 100, 10)])
    prepare(b.root, gtfs, out, ["7"])
    q = quality(out)
    assert q["range"]["from"] == "2026-11-04" and q["range"]["to"] == "2026-11-10"
    skipped = {d["date"] for d in q["range"]["skipped_days"]}
    assert skipped == {"2026-11-03", "2026-11-11"}


def test_from_to_narrow_the_range(world):
    b, gtfs, out = world
    b.add("2026-11-05T10:00:20Z", [vehicle(utc("2026-11-05T10:00:00Z"), 100, 10, start="2026-11-05T09:50:00Z")])
    prepare(b.root, gtfs, out, ["7"], "--from", "2026-11-05", "--to", "2026-11-06")
    q = quality(out)
    assert (q["range"]["from"], q["range"]["to"]) == ("2026-11-05", "2026-11-06")


def test_identical_repeats_are_deduplicated_keeping_all_sources(world):
    b, gtfs, out = world
    rec = vehicle(T0, 100, 10)
    for slot in ("2026-11-10T10:00:20Z", "2026-11-10T10:00:40Z"):
        b.add(slot, [rec])
    prepare(b.root, gtfs, out, ["7"])
    obs = rows(out, "select id from observations where line='7'")
    assert len(obs) == 1
    srcs = rows(out, "select source_id from obs_sources where obs_id=?", obs[0]["id"])
    assert len(srcs) == 2
    assert quality(out)["lines"]["7"]["raw_records"] == 2


def test_version_without_assignment_is_not_a_conflict(world):
    b, gtfs, out = world
    rec = vehicle(T0, 100, 10)
    b.add("2026-11-10T10:00:20Z", [rec])
    b.add("2026-11-10T10:00:40Z", [unassigned(rec)])
    prepare(b.root, gtfs, out, ["7"])
    obs = rows(out, "select * from observations where line='7'")
    assert len(obs) == 1 and obs[0]["status"] == "ok" and obs[0]["trip_id"] == 5
    assert len(rows(out, "select * from obs_sources where obs_id=?", obs[0]["id"])) == 2


def test_different_assignments_or_measurements_are_conflicts(world):
    b, gtfs, out = world
    a = vehicle(T0, 100, 10)
    b.add("2026-11-10T10:00:20Z", [a, vehicle(T0 + timedelta(seconds=20), 200, 10)])
    b.add("2026-11-10T10:00:40Z", [dict(a, tripId=6), dict(vehicle(T0 + timedelta(seconds=20), 200, 10), delay=99)])
    b.add("2026-11-10T10:01:00Z", [vehicle(T0 + timedelta(seconds=300), 300, 10)])
    prepare(b.root, gtfs, out, ["7"])
    obs = rows(out, "select status, conflict_reason, course_id from observations where line='7' and status='conflict'")
    assert len(obs) == 2
    assert all(o["course_id"] is None for o in obs)
    assert quality(out)["lines"]["7"]["conflicts"] == 2


def test_missing_manifest_is_provenance_gap_but_data_is_used(world):
    b, gtfs, out = world
    b.add("2026-11-10T10:00:20Z", [vehicle(T0, 100, 10)], manifest=False)
    prepare(b.root, gtfs, out, ["7"])
    q = quality(out)
    assert q["counts"]["provenance_gaps"] == 1
    assert len(rows(out, "select * from observations where line='7'")) == 1
    assert rows(out, "select provenance_gap from sources where snapshot_key like '%10:00:20%'")[0]["provenance_gap"] == 1


def test_partial_manifest_keeps_valid_gps(world):
    b, gtfs, out = world
    b.add("2026-11-10T10:00:20Z", [vehicle(T0, 100, 10)], status="partial")
    prepare(b.root, gtfs, out, ["7"])
    src = rows(out, "select run_status, source_status from sources where snapshot_key like '%10:00:20%'")[0]
    assert src == {"run_status": "partial", "source_status": "stored"}
    assert len(rows(out, "select * from observations where line='7'")) == 1


def test_corrupt_snapshot_is_reported_and_run_continues(world):
    b, gtfs, out = world
    b.add("2026-11-10T10:00:20Z", [vehicle(T0, 100, 10)], corrupt=True)
    b.add("2026-11-10T10:00:40Z", [vehicle(T0 + timedelta(seconds=20), 200, 10)])
    prepare(b.root, gtfs, out, ["7"])
    assert quality(out)["counts"]["snapshot_errors"] == 1
    assert len(rows(out, "select * from observations where line='7'")) == 1


def test_zero_delay_is_kept_and_missing_delay_is_null(world):
    b, gtfs, out = world
    b.add("2026-11-10T10:00:20Z", [vehicle(T0, 100, 0), vehicle(T0 + timedelta(seconds=20), 120, None)])
    prepare(b.root, gtfs, out, ["7"])
    delays = [r["delay"] for r in rows(out, "select delay from observations where line='7' order by t_utc")]
    assert delays == [0, None]


def test_alphanumeric_and_other_lines_work_without_code_changes(world):
    b, gtfs, out = world
    b.add("2026-11-10T10:00:20Z", [vehicle(T0, 100, 5, line="N8", route_id=8, trip=6, lat=54.36, vehicle_id=3,
                                          service="008-01"), vehicle(T0, 100, 5)])
    prepare(b.root, gtfs, out, ["N8"])
    assert {r["line"] for r in rows(out, "select line from observations")} == {"N8"}
    prepare(b.root, gtfs, out, ["N8", "7"])
    assert {r["line"] for r in rows(out, "select line from observations")} == {"N8", "7"}


def test_records_without_course_are_counted_per_line_deduplicated(world):
    b, gtfs, out = world
    rec = unassigned(vehicle(T0, 100, 0))
    b.add("2026-11-10T10:00:10Z", [vehicle(T0 + timedelta(seconds=60), 300, 5)])
    b.add("2026-11-10T10:00:20Z", [rec])
    b.add("2026-11-10T10:00:40Z", [rec])
    prepare(b.root, gtfs, out, ["7"])
    ql = quality(out)["lines"]["7"]
    assert ql["skipped_records"] == 1 and ql["raw_skipped_records"] == 2


def test_rerun_after_failure_keeps_previous_result(world):
    b, gtfs, out = world
    b.add("2026-11-10T10:00:20Z", [vehicle(T0, 100, 10)])
    prepare(b.root, gtfs, out, ["7"])
    before = out.read_bytes()
    with pytest.raises(SystemExit):
        prepare(b.root, gtfs, out, ["7"], "--from", "2030-01-01", "--to", "2030-01-02")
    assert out.read_bytes() == before
    prepare(b.root, gtfs, out, ["7"])
    assert out.exists()


def test_observations_outside_processed_days_are_ignored(world):
    b, gtfs, out = world
    b.add("2026-11-11T07:36:20Z", [vehicle(utc("2026-11-11T07:36:00Z"), 100, 10)])
    with pytest.raises(SystemExit):
        prepare(b.root, gtfs, out, ["7"])   # brak użytecznych danych w przetwarzanym zakresie
    assert not out.exists()


def test_uninterpretable_record_is_counted_and_does_not_stop_the_run(world):
    b, gtfs, out = world
    good = vehicle(T0, 100, 10)
    b.add("2026-11-10T10:00:20Z", [good, dict(vehicle(T0 + timedelta(seconds=20), 120, 5), scheduledTripStartTime="to nie data")])
    prepare(b.root, gtfs, out, ["7"])
    assert quality(out)["counts"]["bad_records"] == 1
    assert len(rows(out, "select * from observations where line='7'")) == 1
