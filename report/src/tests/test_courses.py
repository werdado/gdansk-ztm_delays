"""Kursy, odcinki, początek kursu i dojazd do krańca – przez `prepare` na syntetycznym archiwum."""
from datetime import timedelta


from helpers import prepare, quality, rows
from world import STANDARD_STEPS, run_scenario, unassigned, utc

BASE = utc("2026-11-10T10:00:00Z")


def put(b, runs, slot="2026-11-10T12:00:00Z"):
    b.add(slot, [rec for run in runs for _, rec in run])


def values(out, line="7"):
    res = {}
    for r in rows(out, """select sv.*, s.from_stop from segment_values sv
                          join segments s on s.line=sv.line and s.id=sv.seg_id where sv.line=?""", line):
        res.setdefault(r["from_stop"], []).append(r)
    return res


def test_standard_run_values_start_changes_and_arrival(world):
    b, gtfs, out = world
    put(b, [run_scenario(BASE, STANDARD_STEPS)])
    prepare(b.root, gtfs, out, ["7"])
    v = values(out)
    assert [(k, v[k][0]["end_delay"], v[k][0]["start_delay"]) for k in ("a0", "a1", "a2", "a3")] == [
        ("a0", 140, 120), ("a1", 160, 140), ("a2", 180, 160), ("a3", 215, 180)]
    assert v["a0"][0]["start_kind"] == "course_start" and v["a1"][0]["start_kind"] == "prev_end"
    assert 35 < v["a0"][0]["end_dist"] < 45 and v["a0"][0]["end_gap"] == 20
    arr = rows(out, "select delay, uncertain from course_arrival")[0]
    assert arr == {"delay": 215, "uncertain": None}
    phases = [r["phase"] for r in rows(out, "select phase from observations order by t_utc")]
    assert phases[:2] == ["pre_departure"] * 2
    assert phases[2:13] == ["en_route"] * 11
    assert phases[13:] == ["terminal_after_arrival"] * 3


def test_phases_do_not_depend_on_delay_values(world):
    b, gtfs, out = world
    shifted = [(o, m, 0 if m >= 1990 else d + 1000, s) for o, m, d, s in STANDARD_STEPS]
    put(b, [run_scenario(BASE, shifted)])
    prepare(b.root, gtfs, out, ["7"])
    phases = [r["phase"] for r in rows(out, "select phase from observations order by t_utc")]
    assert phases.count("pre_departure") == 2 and phases.count("terminal_after_arrival") == 3
    assert values(out)["a3"][0]["end_delay"] == 1215


def test_segment_crossed_entirely_between_two_observations_has_no_value(world):
    b, gtfs, out = world
    steps = [s for s in STANDARD_STEPS if s[1] not in (660, 860)]   # brak obserwacji wewnątrz odcinka 1
    put(b, [run_scenario(BASE, steps)])
    prepare(b.root, gtfs, out, ["7"])
    v = values(out)
    assert "a1" not in v          # nie przypisujemy wartości z sąsiedztwa
    assert "a0" in v
    note = rows(out, "select note from segment_passes sp join segments s on s.id=sp.seg_id where s.from_stop='a1'")
    assert note and "całości" in note[0]["note"]


def test_gap_over_60s_at_stop_gives_no_value(world):
    b, gtfs, out = world
    steps = [(o + (50 if i >= 5 else 0), m, d, sp) for i, (o, m, d, sp) in enumerate(STANDARD_STEPS)]
    put(b, [run_scenario(BASE, steps)])
    prepare(b.root, gtfs, out, ["7"])
    assert "a0" not in values(out)   # przerwa 70 s > 60 s wokół granicy przystanku


def test_stationary_scatter_around_pole_does_not_change_result(world):
    b, gtfs, out = world
    # postój wokół słupka 1000 (przystanek a2): obserwacje 985–1010 m należą do następnego odcinka
    base = list(STANDARD_STEPS)
    scatter = base[:7] + [(130, 990, 165, 0), (140, 1004, 166, 0), (150, 995, 167, 0)] + [(o + 40, m, d, sp) for o, m, d, sp in base[7:]]
    put(b, [run_scenario(BASE, scatter)])
    prepare(b.root, gtfs, out, ["7"])
    # ostatnia obserwacja przed granicą 975 to 860 (160), następna to 990 (za granicą, 10 s później)
    assert values(out)["a1"][0]["end_delay"] == 160


def test_first_observation_already_moving_gives_level_without_change(world):
    b, gtfs, out = world
    steps = [s for s in STANDARD_STEPS if s[0] >= 40]
    put(b, [run_scenario(BASE, steps)])
    prepare(b.root, gtfs, out, ["7"])
    a0 = values(out)["a0"][0]
    assert a0["end_delay"] == 140 and a0["start_delay"] == 120   # pierwsza obserwacja w ruchu jest początkiem


def test_first_observation_beyond_150m_means_unknown_start(world):
    b, gtfs, out = world
    steps = [(o, m, d, sp) for o, m, d, sp in STANDARD_STEPS if m >= 260]
    put(b, [run_scenario(BASE, steps)])
    prepare(b.root, gtfs, out, ["7"])
    a0 = values(out).get("a0")
    assert a0 is not None and a0[0]["end_delay"] == 140 and a0[0]["start_delay"] is None   # poziom bez zmiany


def test_first_moving_observation_farther_than_150m_gives_no_start(world):
    b, gtfs, out = world
    steps = [(0, 5, 100, 0), (20, 440, 130, 10), (40, 520, 140, 10), (60, 760, 150, 10)]
    put(b, [run_scenario(BASE, steps)])
    prepare(b.root, gtfs, out, ["7"])
    a0 = values(out)["a0"][0]
    assert a0["end_delay"] == 130 and a0["start_delay"] is None  # 440 m jest dalej niż 150 m od słupka


def test_moving_zero_near_terminal_does_not_replace_arrival_value(world):
    b, gtfs, out = world
    put(b, [run_scenario(BASE, STANDARD_STEPS)])
    prepare(b.root, gtfs, out, ["7"])
    last = rows(out, "select delay from observations where phase='terminal_after_arrival'")
    assert {r["delay"] for r in last} == {0}
    assert values(out)["a3"][0]["end_delay"] == 215


def test_first_observation_already_stationary_at_terminal_is_uncertain(world):
    b, gtfs, out = world
    steps = [(0, 1995, 0, 0), (20, 1996, 0, 0)]
    put(b, [run_scenario(BASE, steps)])
    prepare(b.root, gtfs, out, ["7"])
    arr = rows(out, "select delay, uncertain from course_arrival")[0]
    assert arr["delay"] is None and arr["uncertain"]


def test_stationary_after_gap_over_60s_leaves_arrival_unknown(world):
    b, gtfs, out = world
    steps = [(0, 1700, 50, 10), (80, 1990, 0, 0)]
    put(b, [run_scenario(BASE, steps)])
    prepare(b.root, gtfs, out, ["7"])
    arr = rows(out, "select delay, uncertain from course_arrival")[0]
    assert arr["delay"] is None and "60 s" in arr["uncertain"]


def test_zero_speed_with_position_jump_and_delay_reset_keeps_arrival_before_reset(world):
    b, gtfs, out = world
    steps = [(0, 1900, 257, 25), (20, 1945, 0, 0), (40, 1946, 0, 0)]   # 45 m przesunięcia, prędkość 0, opóźnienie 0
    put(b, [run_scenario(BASE, steps)])
    prepare(b.root, gtfs, out, ["7"])
    arr = rows(out, "select delay, uncertain from course_arrival")[0]
    assert arr == {"delay": 257, "uncertain": None}


def test_vehicle_change_breaks_continuity_for_change(world):
    b, gtfs, out = world
    a = run_scenario(BASE, STANDARD_STEPS[:6])
    other = run_scenario(BASE, STANDARD_STEPS[6:], vehicle_id=101)
    put(b, [a, other])
    prepare(b.root, gtfs, out, ["7"])
    assert len(rows(out, "select * from fragments")) == 2
    v = values(out)
    assert "a1" in v and v["a1"][0]["start_delay"] is None  # początek odcinka w innym fragmencie


def test_momentary_loss_of_assignment_does_not_split_course(world):
    b, gtfs, out = world
    run = run_scenario(BASE, STANDARD_STEPS)
    t, rec = run[5]
    run[5] = (t, unassigned(rec))
    put(b, [run])
    prepare(b.root, gtfs, out, ["7"])
    assert len(rows(out, "select * from fragments")) == 1
    assert quality(out)["lines"]["7"]["skipped_records"] == 1


def test_variant_absent_in_gtfs_is_reported_without_values(world):
    b, gtfs, out = world
    run = run_scenario(BASE, STANDARD_STEPS, trip=99)
    put(b, [run])
    prepare(b.root, gtfs, out, ["7"])
    assert values(out) == {}
    q = quality(out)["lines"]["7"]["variants_absent_in_gtfs"]
    assert q[0]["variant"] == "7-99" and q[0]["courses"] == 1 and q[0]["observations"] == len(STANDARD_STEPS)
    assert rows(out, "select variant_status from courses")[0]["variant_status"] == "absent_in_gtfs"


def test_route_id_missing_in_gtfs_keeps_line_membership(world):
    b, gtfs, out = world
    put(b, [run_scenario(BASE, STANDARD_STEPS, line="171", route_id=10171, trip=5, service="171-01")])
    prepare(b.root, gtfs, out, ["171"])
    assert len(rows(out, "select * from observations where line='171'")) == len(STANDARD_STEPS)
    assert quality(out)["lines"]["171"]["variants_absent_in_gtfs"]


def test_overlapping_assignments_of_one_course_by_two_vehicles_are_excluded(world):
    b, gtfs, out = world
    a = run_scenario(BASE, STANDARD_STEPS)
    c = run_scenario(BASE + timedelta(seconds=5), STANDARD_STEPS, vehicle_id=555)
    put(b, [a, c])
    prepare(b.root, gtfs, out, ["7"])
    assert values(out) == {}
    assert {r["status"] for r in rows(out, "select status from fragments")} == {"parallel_conflict"}


def test_vehicle_going_a_different_way_is_flagged_as_mismatched_variant(world):
    b, gtfs, out = world
    run = run_scenario(BASE, STANDARD_STEPS, lat=54.40)
    put(b, [run])
    prepare(b.root, gtfs, out, ["7"])
    assert values(out) == {}
    assert rows(out, "select status from fragments")[0]["status"] == "variant_mismatch"
    assert all(r["seg_id"] is None for r in rows(out, "select seg_id from observations"))


def test_ambiguous_gtfs_variant_is_excluded(tmp_path):
    from world import ArchiveBuilder, write_gtfs
    gtfs = tmp_path / "g.zip"
    write_gtfs(gtfs, extra_variant_shapes=True)
    b = ArchiveBuilder(tmp_path / "a")
    b.add_boundaries()
    put(b, [run_scenario(BASE, STANDARD_STEPS)])
    out = tmp_path / "o" / "d.sqlite"
    prepare(b.root, gtfs, out, ["7"])
    assert values(out) == {}
    assert rows(out, "select status from variants where line='7'")[0]["status"] == "ambiguous"


def test_course_cut_by_range_boundary_is_marked(world):
    b, gtfs, out = world
    run = run_scenario(utc("2026-11-10T22:58:30Z"), [(0, 100, 5, 10), (20, 300, 5, 10)], start="2026-11-10T22:50:00Z")
    put(b, [run], slot="2026-11-10T22:59:00Z")
    prepare(b.root, gtfs, out, ["7"])
    assert rows(out, "select truncated from courses")[0]["truncated"] == "end"


def test_fragment_that_never_reached_the_terminal_has_no_last_segment_note(world):
    b, gtfs, out = world
    put(b, [run_scenario(BASE, STANDARD_STEPS[:9])])     # kończy się przed ostatnim odcinkiem
    prepare(b.root, gtfs, out, ["7"])
    notes = rows(out, "select note from segment_passes sp join segments s on s.id=sp.seg_id where s.from_stop='a3'")
    assert notes == []


def test_segment_seen_by_two_fragments_of_one_course_is_listed_once_with_its_value(world):
    b, gtfs, out = world
    first = run_scenario(BASE, STANDARD_STEPS[:10])                                     # a2 z wartością 180
    second = run_scenario(BASE + timedelta(seconds=400), [(0, 1260, 180, 10), (70, 1480, 190, 10)], vehicle_id=101)
    put(b, [first, second])                                                            # drugi fragment: przerwa 70 s > 60 s
    prepare(b.root, gtfs, out, ["7"])
    assert len(rows(out, "select * from fragments")) == 2
    a2 = rows(out, "select sp.has_value, sp.note from segment_passes sp join segments s on s.id=sp.seg_id where s.from_stop='a2'")
    assert a2 == [{"has_value": 1, "note": a2[0]["note"]}]
