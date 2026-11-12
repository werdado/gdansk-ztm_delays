"""Grupowanie obserwacji w kursy i ciągłe fragmenty (pojazd i wariant to przypisania fragmentów)."""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from dataclasses import dataclass, field

from .ingest import Obs
from .params import Params


@dataclass
class Fragment:
    obs: list[Obs]
    status: str = "ok"
    note: str | None = None
    match_fraction: float | None = None
    id: int = 0

    @property
    def t0(self) -> int:
        return self.obs[0].t

    @property
    def t1(self) -> int:
        return self.obs[-1].t

    @property
    def vehicle_id(self) -> int:
        return self.obs[0].vehicle_id

    @property
    def variant(self) -> tuple[int | None, int]:
        return self.obs[0].route_id, self.obs[0].trip_id


@dataclass
class Course:
    line: str
    service: str
    sched_start: int
    fragments: list[Fragment] = field(default_factory=list)
    id: int = 0
    dir: int | None = None
    variant_key: str | None = None
    variant_status: str | None = None
    truncated: str | None = None

    @property
    def n_obs(self) -> int:
        return sum(len(f.obs) for f in self.fragments)


def build(obs: list[Obs], params: Params, range_start: int, range_end: int) -> list[Course]:
    conflicts: dict[tuple[str, int], list[int]] = defaultdict(list)
    for o in obs:
        if o.status == "conflict":
            conflicts[(o.line, o.vehicle_id)].append(o.t)
    for v in conflicts.values():
        v.sort()
    by_course: dict[tuple, list[Obs]] = defaultdict(list)
    for o in obs:
        if o.status == "ok" and o.assigned:
            by_course[(o.line, o.vehicle_service or "", o.sched_start)].append(o)
    courses: list[Course] = []
    for (line, service, start), items in by_course.items():
        items.sort(key=lambda o: (o.t, o.vehicle_id))
        c = Course(line, service, start)
        # fragmenty: kolejne obserwacje tego samego pojazdu i wariantu bez przerwy i bez konfliktu
        open_frags: dict[int, Fragment] = {}
        for o in items:
            f = open_frags.get(o.vehicle_id)
            if f is not None:
                last = f.obs[-1]
                cts = conflicts.get((line, o.vehicle_id), [])
                broken = (o.t - last.t > params.gap_break_s or (o.route_id, o.trip_id) != (last.route_id, last.trip_id)
                          or bisect_right(cts, o.t - 1) > bisect_right(cts, last.t))
                if broken:
                    f = None
            if f is None:
                f = Fragment([])
                c.fragments.append(f)
                open_frags[o.vehicle_id] = f
            f.obs.append(o)
        c.fragments.sort(key=lambda f: (f.t0, f.vehicle_id))
        _mark_parallel(c)
        courses.append(c)
    courses.sort(key=lambda c: (c.line, c.sched_start, c.service))
    for i, c in enumerate(courses, 1):
        c.id = i
        _truncation(c, params, range_start, range_end)
    return courses


def _mark_parallel(c: Course) -> None:
    """Sprzeczne, równoległe przypisania tego samego kursu do różnych pojazdów wyłączają fragmenty."""
    fr = c.fragments
    for i, a in enumerate(fr):
        for b in fr[i + 1:]:
            if a.vehicle_id != b.vehicle_id and a.t0 <= b.t1 and b.t0 <= a.t1:
                for f in (a, b):
                    f.status, f.note = "parallel_conflict", "równoległe przypisanie kursu do różnych pojazdów"


def _truncation(c: Course, params: Params, range_start: int, range_end: int) -> None:
    t1 = max(f.t1 for f in c.fragments)
    start = c.sched_start < range_start
    end = t1 >= range_end - params.gap_break_s
    c.truncated = "both" if start and end else "start" if start else "end" if end else None
