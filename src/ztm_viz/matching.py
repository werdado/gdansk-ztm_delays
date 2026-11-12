"""Dopasowanie kolejnościowe obserwacji fragmentu do trasy wariantu (Viterbi z oznaczaniem niejednoznaczności)."""
from __future__ import annotations

from dataclasses import dataclass

from .params import Params
from .route import Route


@dataclass(slots=True)
class Match:
    s: float            # chainage wzdłuż trasy
    dist: float         # odległość od trasy
    ambiguous: bool = False


def match_fragment(route: Route, pts: list[tuple[float, float, int]], params: Params) -> list[Match | None]:
    """pts: (x, y, t) w kolejności czasu. Zwraca dopasowanie dla każdej obserwacji albo None
    (poza trasą). Niejednoznaczne rzutowanie ma `ambiguous=True`; obserwacje niejednoznaczne
    nie służą do wyznaczania przejść przez granice."""
    n = len(pts)
    cands = [route.candidates(x, y, params.match_max_dist_m) for x, y, _ in pts]
    out: list[Match | None] = [None] * n
    vmax = params.max_speed_kmh / 3.6
    # łańcuchy ciągłych obserwacji z kandydatami
    chain: list[int] = []
    last_t = None

    def flush():
        if chain:
            _solve(route, chain, pts, cands, out, params, vmax)

    for i in range(n):
        if not cands[i]:
            continue
        if chain and pts[i][2] - last_t > params.gap_break_s:
            flush()
            chain = []
        chain.append(i)
        last_t = pts[i][2]
        # rozbicie przy braku dopuszczalnego przejścia wykonuje _solve
    flush()
    return out


def feasible(prev_s: float, s: float, dt: int, params: Params, vmax: float) -> bool:
    ds = s - prev_s
    return ds >= -params.backtrack_tol_m and ds <= vmax * dt + params.speed_margin_m


def _solve(route, chain, pts, cands, out, params, vmax):
    # podział na podłańcuchy, gdy żaden stan nie jest osiągalny
    start = 0
    while start < len(chain):
        end = _forward_extent(chain, start, pts, cands, params, vmax)
        _solve_one(route, chain[start:end], pts, cands, out, params, vmax)
        start = end


def _forward_extent(chain, start, pts, cands, params, vmax) -> int:
    reach = [c for c in cands[chain[start]]]
    k = start + 1
    while k < len(chain):
        i, p = chain[k], chain[k - 1]
        dt = pts[i][2] - pts[p][2]
        nxt = [c for c in cands[i] if any(feasible(pc[0], c[0], dt, params, vmax) for pc in reach)]
        if not nxt:
            return k
        reach = nxt
        k += 1
    return k


def _solve_one(route, chain, pts, cands, out, params, vmax):
    m = len(chain)
    INF = float("inf")
    fwd = [[c[1] for c in cands[chain[0]]]]
    for k in range(1, m):
        dt = pts[chain[k]][2] - pts[chain[k - 1]][2]
        row = []
        for c in cands[chain[k]]:
            best = INF
            for j, pc in enumerate(cands[chain[k - 1]]):
                if feasible(pc[0], c[0], dt, params, vmax):
                    best = min(best, fwd[k - 1][j])
            row.append(best + c[1])
        fwd.append(row)
    bwd = [[0.0] * len(cands[i]) for i in chain]
    for k in range(m - 2, -1, -1):
        dt = pts[chain[k + 1]][2] - pts[chain[k]][2]
        for j, c in enumerate(cands[chain[k]]):
            best = INF
            for jj, nc in enumerate(cands[chain[k + 1]]):
                if feasible(c[0], nc[0], dt, params, vmax):
                    best = min(best, nc[1] + bwd[k + 1][jj])
            bwd[k][j] = best
    for k, i in enumerate(chain):
        totals = [fwd[k][j] + bwd[k][j] for j in range(len(cands[i]))]
        jbest = min(range(len(totals)), key=totals.__getitem__)
        if totals[jbest] == INF:
            continue
        s, d = cands[i][jbest]
        seg_best = route.segment_index(s)
        ambiguous = False
        for j, tot in enumerate(totals):
            if j == jbest or tot == INF:
                continue
            if route.segment_index(cands[i][j][0]) != seg_best and tot <= totals[jbest] + params.ambiguity_margin_m:
                ambiguous = True
        out[i] = Match(s, d, ambiguous)
