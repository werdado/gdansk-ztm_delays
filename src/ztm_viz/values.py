"""Wartości przy końcu odcinków, początek kursu i dojazd do krańca dla jednego fragmentu kursu.

Reguły: ADR 0003 i 0005 oraz plan (sekcja 3). Wartość `delay` nie uczestniczy w rozpoznawaniu fazy."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from .matching import Match, feasible
from .params import Params
from .route import Route


@dataclass(slots=True)
class PObs:
    """Obserwacja fragmentu w postaci wejściowej dla reguł (czas, opóźnienie, prędkość, pozycja w metrach)."""
    t: int
    delay: int | None
    speed: float | None
    x: float
    y: float


@dataclass(slots=True)
class SegValue:
    seg: int
    end_i: int
    end_delay: int
    dist: float
    gap: int
    start_i: int | None = None
    start_delay: int | None = None
    start_kind: str | None = None


@dataclass(slots=True)
class SegPass:
    has_value: bool
    has_change: bool
    note: str | None


@dataclass(slots=True)
class Arrival:
    i: int | None
    delay: int | None
    uncertain: str | None


@dataclass
class FragResult:
    values: dict[int, SegValue] = field(default_factory=dict)
    passes: dict[int, SegPass] = field(default_factory=dict)
    phases: list[str] = field(default_factory=list)
    arrival: Arrival = field(default_factory=lambda: Arrival(None, None, "brak danych"))
    start_i: int | None = None


def _moving_flags(obs: list[PObs], params: Params) -> list[bool]:
    """Oznaka ruchu: raportowana prędkość; przesunięcie pozycji tylko wtedy, gdy prędkości brak.

    Diagnostyka pełnego tygodnia 127/162 (etap 2): przy uznawaniu przesunięcia >20 m za ruch 81% wyznaczonych
    dojazdów (996 z 1231) miało opóźnienie 0, czyli wartość po skoku opóźnienia do zera przy krańcu; przy samej
    prędkości 45% (631 z 1412), a dojazdów rozstrzygniętych jest więcej."""
    flags = []
    for i, o in enumerate(obs):
        if o.speed is not None:
            moved = o.speed > 0
        elif i > 0:
            p = obs[i - 1]
            moved = math.hypot(o.x - p.x, o.y - p.y) > params.move_shift_m
        else:
            moved = False
        flags.append(moved)
    return flags


def analyze(route: Route, obs: list[PObs], matches: list[Match | None], params: Params) -> FragResult:
    m = len(obs)
    res = FragResult(phases=["en_route"] * m)
    n = route.n_segments
    moving = _moving_flags(obs, params)
    known = [mt is not None and not mt.ambiguous for mt in matches]
    s = [mt.s if mt is not None else None for mt in matches]
    vmax = params.max_speed_kmh / 3.6

    # ---- standardowe wartości przy końcu odcinków 0..n-2 ------------------------------------
    for j in range(1, n):                       # granica przystanku j kończy odcinek j-1
        seg = j - 1
        B = route.boundary(j)
        traversed = _traversed(s, B)
        if not traversed:
            continue
        pair = None
        for i in range(m - 1):
            if known[i] and known[i + 1] and s[i] < B <= s[i + 1]:
                pair = i
                break
        if pair is None:
            res.passes[seg] = SegPass(False, False, "brak pary obserwacji wokół granicy przystanku końcowego")
            continue
        i = pair
        gap = obs[i + 1].t - obs[i].t
        if not feasible(s[i], s[i + 1], gap, params, vmax):
            res.passes[seg] = SegPass(False, False, "niewiarygodny przyrost drogi między obserwacjami")
        elif s[i] < route.boundary(seg):
            res.passes[seg] = SegPass(False, False, "odcinek przejechany w całości między dwiema obserwacjami")
        elif gap > params.crossing_gap_s:
            res.passes[seg] = SegPass(False, False, "przerwa między obserwacjami przy przystanku przekracza 60 s")
        elif obs[i].delay is None:
            res.passes[seg] = SegPass(False, False, "brak raportowanego opóźnienia w obserwacji")
        else:
            res.values[seg] = SegValue(seg, i, obs[i].delay, route.stop_chain[j] - s[i], gap)

    # ---- początek kursu -----------------------------------------------------------------------
    c0 = route.stop_chain[0]
    b1 = route.boundary(1)
    for i in range(m):
        if known[i] and moving[i] and abs(s[i] - c0) <= params.start_zone_m and s[i] < b1:
            if obs[i].delay is not None:
                res.start_i = i
            else:
                res.start_i = -1  # ruch rozpoznany, ale bez wartości opóźnienia
            break
    start_idx = res.start_i

    # ---- dojazd do krańca ---------------------------------------------------------------------
    res.arrival = _arrival(route, obs, s, known, moving, params, start_idx)
    last = n - 1
    arr = res.arrival
    if arr.i is not None and arr.delay is not None:
        sa = s[arr.i]
        if sa is not None and sa >= route.boundary(last):
            res.values[last] = SegValue(last, arr.i, arr.delay, max(route.stop_chain[n] - sa, 0.0), obs[arr.i + 1].t - obs[arr.i].t)
        else:
            res.passes[last] = SegPass(False, False, "obserwacja dojazdu leży przed ostatnim odcinkiem")
    elif _traversed(s, route.boundary(n)):
        res.passes.setdefault(last, SegPass(False, False, "dojazd do krańca nierozstrzygnięty: " + (arr.uncertain or "brak danych")))

    # ---- początki odcinków i zmiany -----------------------------------------------------------------
    for seg, v in res.values.items():
        if seg == 0:
            if res.start_i is not None and res.start_i >= 0 and res.start_i != v.end_i:
                v.start_i, v.start_delay, v.start_kind = res.start_i, obs[res.start_i].delay, "course_start"
        elif (prev := res.values.get(seg - 1)) is not None and prev.end_i != v.end_i:
            v.start_i, v.start_delay, v.start_kind = prev.end_i, prev.end_delay, "prev_end"
    for seg, v in res.values.items():
        note = None if v.start_delay is not None else (
            "początek odcinka nieznany – zmiana niedostępna" if seg > 0 or res.start_i is None or res.start_i < 0
            else "początek i koniec odcinka z tej samej obserwacji – zmiana nieznana")
        res.passes[seg] = SegPass(True, v.start_delay is not None, note)

    # ---- fazy -------------------------------------------------------------------------------
    _phases(res, route, obs, s, known, moving, params, start_idx)
    return res


def _traversed(s: list, B: float) -> bool:
    vals = [x for x in s if x is not None]
    return bool(vals) and min(vals) < B <= max(vals)


def _arrival(route: Route, obs, s, known, moving, params: Params, start_idx) -> Arrival:
    n = route.n_segments
    stop = route.stop_xy[n]
    cn = route.stop_chain[n]
    first_stat = None
    for i, o in enumerate(obs):
        if s[i] is None or s[i] < cn - params.terminal_zone_m - params.stop_boundary_m:
            continue
        if math.hypot(o.x - stop[0], o.y - stop[1]) > params.terminal_zone_m:
            continue
        if start_idx is not None and start_idx >= 0 and i <= start_idx:
            continue
        if not moving[i]:
            first_stat = i
            break
    if first_stat is None:
        return Arrival(None, None, "brak postoju w okolicy krańca (kurs niedokończony w danych)")
    i = first_stat
    if i == 0:
        return Arrival(None, None, "pierwsza obserwacja już podczas postoju przy krańcu")
    prev = i - 1
    if obs[i].t - obs[prev].t > params.terminal_gap_s:
        return Arrival(None, None, "przerwa między ostatnią obserwacją w ruchu a postojem przekracza 60 s")
    if not moving[prev]:
        return Arrival(None, None, "zastana pozycja postojowa przed krańcem – dojazd niejednoznaczny")
    if obs[prev].delay is None:
        return Arrival(None, None, "brak raportowanego opóźnienia w obserwacji dojazdu")
    return Arrival(prev, obs[prev].delay, None)


def _phases(res: FragResult, route: Route, obs, s, known, moving, params: Params, start_idx) -> None:
    m = len(obs)
    c0 = route.stop_chain[0]
    ph = res.phases
    if start_idx is not None and start_idx >= 0:
        for i in range(start_idx):
            near = s[i] is not None and abs(s[i] - c0) <= params.start_zone_m
            ph[i] = "pre_departure" if (near and not moving[i]) else "unknown"
    elif start_idx is None:
        for i in range(m):
            if s[i] is not None and abs(s[i] - c0) <= params.start_zone_m and not moving[i]:
                ph[i] = "pre_departure"
            else:
                break
    for i in range(m):
        if s[i] is None and ph[i] == "en_route":
            ph[i] = "unknown"
    arr = res.arrival
    if arr.i is not None:
        for i in range(arr.i + 1, m):
            ph[i] = "terminal_after_arrival"
    else:
        n = route.n_segments
        stop = route.stop_xy[n]
        for i in range(m):
            if s[i] is not None and not moving[i] and math.hypot(obs[i].x - stop[0], obs[i].y - stop[1]) <= params.terminal_zone_m \
                    and s[i] >= route.stop_chain[n] - params.terminal_zone_m - params.stop_boundary_m:
                ph[i] = "unknown"
