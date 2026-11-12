"""Parametry reguł przygotowania (początkowe założenia, zatwierdzane diagnostyką etapu 2)."""
from __future__ import annotations

from dataclasses import asdict, dataclass

RULES_VERSION = "1"
TIMEZONE = "Europe/Warsaw"


@dataclass(frozen=True)
class Params:
    match_max_dist_m: float = 75.0       # odległość od geometrii
    backtrack_tol_m: float = 30.0        # tolerancja cofnięcia
    gap_break_s: int = 90                # przerwa ciągłości
    max_speed_kmh: float = 100.0         # maksymalny przyrost drogi: prędkość + margines
    speed_margin_m: float = 30.0
    stop_boundary_m: float = 25.0        # granica przystanku przed rzutem słupka
    crossing_gap_s: int = 60             # przerwa między obserwacjami wyznaczającymi przejazd przez przystanek
    start_zone_m: float = 150.0          # strefa początku kursu
    terminal_zone_m: float = 150.0       # strefa krańca
    terminal_gap_s: int = 60
    move_shift_m: float = 20.0           # przesunięcie pozycji uznawane za ruch
    ambiguity_margin_m: float = 10.0     # różnica kosztu rzutowań uznawana za niejednoznaczność
    min_match_fraction: float = 0.5      # poniżej: wariant niezgodny z przejazdem
    day_tolerance_s: int = 60            # tolerancja początku i końca doby
    merge_path_tol_m: float = 15.0       # zgodność przebiegu odcinków różnych wariantów

    def as_dict(self) -> dict:
        return asdict(self)
