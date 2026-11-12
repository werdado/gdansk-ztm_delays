"""Geometria wariantu w metrach: rzut słupków i obserwacji na trasę z zachowaniem kolejności."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from pyproj import Transformer

from .gtfs import GtfsVariant
from .params import Params


@lru_cache(maxsize=1)
def _fwd() -> Transformer:
    # Układ PL-1992 (EPSG:2180) – metryczny dla całej Polski; always_xy: (lon, lat)
    return Transformer.from_crs("EPSG:4326", "EPSG:2180", always_xy=True)


@lru_cache(maxsize=1)
def _inv() -> Transformer:
    return Transformer.from_crs("EPSG:2180", "EPSG:4326", always_xy=True)


def project(lon, lat):
    return _fwd().transform(lon, lat)


def unproject(x, y):
    lon, lat = _inv().transform(x, y)
    return lat, lon


def _dedupe_points(xy: np.ndarray) -> np.ndarray:
    keep = [0]
    for i in range(1, len(xy)):
        if np.hypot(*(xy[i] - xy[keep[-1]])) > 0.01:
            keep.append(i)
    return xy[keep]


@dataclass
class Route:
    xy: np.ndarray                      # wierzchołki (N,2) [m]
    cum: np.ndarray                     # skumulowana długość (N,)
    stop_xy: np.ndarray                 # (K,2)
    stop_chain: list[float] = field(default_factory=list)   # odległość słupka wzdłuż trasy
    stop_dist: list[float] = field(default_factory=list)    # odległość słupka od trasy
    params: Params = field(default_factory=Params)

    @classmethod
    def build(cls, variant: GtfsVariant, params: Params) -> "Route":
        lon = [p[1] for p in variant.shape]
        lat = [p[0] for p in variant.shape]
        x, y = project(lon, lat)
        xy = _dedupe_points(np.column_stack([x, y]))
        seg = np.hypot(*(xy[1:] - xy[:-1]).T)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        sx, sy = project([s.lon for s in variant.stops], [s.lat for s in variant.stops])
        r = cls(xy, cum, np.column_stack([sx, sy]), params=params)
        r._place_stops()
        return r

    @property
    def length(self) -> float:
        return float(self.cum[-1])

    def _project_all(self, px: float, py: float):
        """Dla każdego odcinka łamanej: (chainage, odległość) najbliższego punktu."""
        a, b = self.xy[:-1], self.xy[1:]
        d = b - a
        l2 = np.einsum("ij,ij->i", d, d)
        t = np.where(l2 > 0, ((px - a[:, 0]) * d[:, 0] + (py - a[:, 1]) * d[:, 1]) / np.where(l2 > 0, l2, 1), 0.0)
        t = np.clip(t, 0.0, 1.0)
        cx, cy = a[:, 0] + t * d[:, 0], a[:, 1] + t * d[:, 1]
        dist = np.hypot(px - cx, py - cy)
        chain = self.cum[:-1] + t * np.sqrt(l2)
        return chain, dist

    def candidates(self, px: float, py: float, max_dist: float, limit: int = 6) -> list[tuple[float, float]]:
        """Konkurujące rzutowania punktu na trasę (chainage, odległość), do `max_dist`."""
        chain, dist = self._project_all(px, py)
        idx = np.nonzero(dist <= max_dist)[0]
        if len(idx) == 0:
            return []
        order = idx[np.argsort(chain[idx])]
        out: list[tuple[float, float]] = []
        for i in order:
            c, dd = float(chain[i]), float(dist[i])
            if out and abs(c - out[-1][0]) < 5.0:
                if dd < out[-1][1]:
                    out[-1] = (c, dd)
            else:
                out.append((c, dd))
        out.sort(key=lambda cd: cd[1])
        return sorted(out[:limit])

    def _place_stops(self) -> None:
        """Kolejność słupków wzdłuż trasy: najmniejsza suma odległości przy niemalejącym chainage."""
        cand_per_stop = []
        for px, py in self.stop_xy:
            chain, dist = self._project_all(px, py)
            dmin = float(dist.min())
            idx = np.nonzero(dist <= dmin + 40.0)[0]
            cands: list[tuple[float, float]] = []
            for i in idx[np.argsort(chain[idx])]:
                c, dd = float(chain[i]), float(dist[i])
                if cands and abs(c - cands[-1][0]) < 5.0:
                    if dd < cands[-1][1]:
                        cands[-1] = (c, dd)
                else:
                    cands.append((c, dd))
            cand_per_stop.append(cands)
        INF = float("inf")
        cost = [[d for _, d in cand_per_stop[0]]]
        back: list[list[int]] = [[-1] * len(cand_per_stop[0])]
        for k in range(1, len(cand_per_stop)):
            row, brow = [], []
            for c, d in cand_per_stop[k]:
                best, bi = INF, -1
                for j, (pc, _) in enumerate(cand_per_stop[k - 1]):
                    if c >= pc - 1.0 and cost[-1][j] < best:
                        best, bi = cost[-1][j], j
                row.append(best + d)
                brow.append(bi)
            cost.append(row)
            back.append(brow)
        j = int(np.argmin(cost[-1]))
        if cost[-1][j] == INF:  # brak monotonicznego rozwiązania – bierz najbliższe rzuty bez ograniczenia
            sel = [min(c, key=lambda cd: cd[1]) for c in cand_per_stop]
            self.stop_chain = [s[0] for s in sel]
            self.stop_dist = [s[1] for s in sel]
            return
        chosen = []
        for k in range(len(cand_per_stop) - 1, -1, -1):
            chosen.append(cand_per_stop[k][j])
            j = back[k][j]
        chosen.reverse()
        self.stop_chain = [c for c, _ in chosen]
        self.stop_dist = [d for _, d in chosen]

    # --- odcinki i granice -------------------------------------------------------------
    @property
    def n_segments(self) -> int:
        return len(self.stop_chain) - 1

    def boundary(self, j: int) -> float:
        """Granica przystanku j – leży `stop_boundary_m` przed rzutem słupka."""
        return self.stop_chain[j] - self.params.stop_boundary_m

    def segment_index(self, s: float) -> int | None:
        """Odcinek j z granicami [B_j, B_{j+1}); przed pierwszą granicą – None, za ostatnią – ostatni odcinek."""
        n = self.n_segments
        if s < self.boundary(0):
            return None
        lo, hi = 0, n - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if s >= self.boundary(mid):
                lo = mid
            else:
                hi = mid - 1
        return lo

    def subpath_latlon(self, a: float, b: float) -> list[tuple[float, float]]:
        pts = [self._point_at(a)]
        for i, c in enumerate(self.cum):
            if a < c < b:
                pts.append(tuple(self.xy[i]))
        pts.append(self._point_at(b))
        return [unproject(x, y) for x, y in pts]

    def _point_at(self, s: float) -> tuple[float, float]:
        s = min(max(s, 0.0), self.length)
        i = int(np.searchsorted(self.cum, s, side="right")) - 1
        i = min(max(i, 0), len(self.xy) - 2)
        seg = self.cum[i + 1] - self.cum[i]
        t = 0.0 if seg == 0 else (s - self.cum[i]) / seg
        p = self.xy[i] + t * (self.xy[i + 1] - self.xy[i])
        return float(p[0]), float(p[1])
