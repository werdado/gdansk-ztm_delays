# Format danych raportu (wersja 1)

Umowa między generatorem (`ztm_viz.export`) a przeglądarką (`src/ztm_viz/web/`). Wszystkie ścieżki są względne wobec katalogu raportu. JSON jest zapisywany w UTF-8, bez wcięć. Czasy `*L` to **czas lokalny Europe/Warsaw jako „sekundy ściennego zegara”**: epoch UTC + przesunięcie strefy w tym momencie. Dzięki temu `Math.floor(L/86400)` to numer lokalnej doby (dni od 1970-01-01), a `L % 86400` to pora dnia w sekundach. Czasy `*U` to zwykły epoch UTC w sekundach. Brak wartości to `null` (nigdy zero zastępcze).

## `data/manifest.json`

```json
{
  "format": 1,
  "generated": "2026-11-12T14:00:00Z",
  "rules_version": "1",
  "range": {"from": "2026-11-04", "to": "2026-11-10", "days": ["2026-11-04", "..."], "skipped_days": ["2026-11-03", "2026-11-11"]},
  "params": {"match_max_dist_m": 75, "...": "..."},
  "lines": [
    {
      "name": "127",
      "slug": "127",
      "skipped_records": 12,
      "courses": 1000,
      "directions": [
        {"id": 0, "label": "Jasień PKM", "other_headsigns": ["Oliwa PKP"],
         "variants": [{"key": "202-41", "route_id": 202, "trip_id": 41, "headsign": "Jasień PKM", "in_gtfs": true,
                       "status": "ok", "courses": 700, "observations": 9000}]}
      ],
      "geometry": "data/lines/127/geometry.json",
      "days": {"2026-11-04": "data/lines/127/days/2026-11-04.json"}
    }
  ],
  "quality": "data/quality.json"
}
```

* `slug` jest bezpieczną nazwą katalogu (URL-encoded nazwa linii). Przeglądarka używa ścieżek z manifestu, nie buduje ich sama.
* `variants[].status`: `ok`, `absent_in_gtfs` (brak wartości odcinków), `ambiguous` (wyłączony). Warianty bez `ok` nie mają odcinków.
* Kierunek (`dir`) = `direction_id` GTFS. Etykieta = cel najczęściej obserwowanego wariantu.
* Lista linii i kierunków pochodzi wyłącznie z przygotowanego zbioru. Warianty bez odcinków (`absent_in_gtfs`, `ambiguous`) nie mają kierunku i są wymienione osobno w `lines[].variants_outside_timetable` (ta sama postać co elementy `variants`, bez `in_gtfs`).

## `data/lines/<slug>/geometry.json`

```json
{
  "format": 1,
  "segments": [
    {"id": 0, "dir": 0, "from": {"stop_id": "1", "name": "Jasień PKM 01", "lat": 54.3, "lon": 18.5},
     "to": {"stop_id": "2", "name": "...", "lat": 0, "lon": 0},
     "length_m": 523.4, "path": [[54.3, 18.5], [54.31, 18.51]]}
  ],
  "variants": [
    {"key": "202-41", "dir": 0, "headsign": "Jasień PKM", "segments": [0, 1, 2]}
  ]
}
```

* Odcinek (`segments[].id`, unikalny w linii) jest skierowany; różne warianty współdzielą id tylko przy zgodnych słupkach i zgodnym przebiegu.
* `variants[].segments` to uporządkowana lista odcinków wariantu (do osi X wykresu: skumulowane `length_m`). Wykres rysuje osobny przebieg dla każdego wariantu, nie łączy odgałęzień.
* `path` to `[lat, lon]` (kolejność Leaflet).

## `data/lines/<slug>/days/<YYYY-MM-DD>.json`

Wkłady kursów do odcinków, pogrupowane według **lokalnej doby obserwacji końca odcinka**. Kurs wnosi najwyżej jedną wartość do danego odcinka.

```json
{
  "format": 1, "line": "127", "date": "2026-11-10",
  "courses": [{"id": 17, "dir": 0, "variant": "202-41", "startL": 1762772400, "vehicle": "145985", "service": "127-02"}],
  "c": {
    "course": [0, 0],
    "seg":    [4, 5],
    "endL":   [1762775000, 1762775100],
    "end":    [300, 310],
    "startL": [1762774900, null],
    "start":  [120, null],
    "dist":   [18.5, 40.2]
  }
}
```

* `c` jest kolumnowy; wszystkie tablice mają równą długość. `course` to indeks w `courses` tego pliku. `end` = opóźnienie przy końcu odcinka [s]; `start` = opóźnienie na początku odcinka [s] (wartość przy końcu poprzedniego odcinka lub początek kursu); `startL`/`start` = `null`, gdy zmiana nieznana. `dist` = odległość wartości końcowej od przystanku [m].
* `courses[].startL` to rozkładowy czas rozpoczęcia (archiwalny).
* Zmiana = `end − start` liczona w kursie; mediana po kursach.

## `data/lines/<slug>/courses/<id>.json` (na żądanie)

```json
{
  "format": 1, "id": 17, "line": "127", "dir": 0, "variant": "202-41", "headsign": "Jasień PKM",
  "vehicle": "145985", "service": "127-02", "startL": 1762772400,
  "truncated": null,
  "variant_status": "ok",
  "segments": [
    {"seg": 4, "end": {"obs": 12, "delay": 300, "dist_m": 18.5, "gap_s": 20},
     "start": {"obs": 8, "delay": 120, "kind": "prev_end"}, "change": 180, "note": null}
  ],
  "arrival": {"obs": 150, "delay": 60, "uncertain": null},
  "observations": [
    {"tL": 1762772400, "tU": 1762768800, "delay": 12, "speed": 0, "lat": 54.3, "lon": 18.5,
     "s": 12.3, "seg": 0, "phase": "pre_departure", "flags": [], "src": [0, 1]}
  ],
  "sources": [
    {"snapshot": "snapshots/gps/2026-11-10/.../x.json.gz", "manifest": "runs/2026-11-10/.../x.json",
     "run_status": "complete", "source_status": "stored", "url": "https://...", "fetchedAt": "2026-11-10T12:00:00.000Z",
     "receivedAt": "...", "storedAt": "...", "provenance_gap": false}
  ]
}
```

* `truncated`: `null`, `"start"`, `"end"` lub `"both"` (kurs obcięty granicą przetwarzanego zakresu dób).
* `observations` w kolejności czasu. `phase`: `pre_departure`, `en_route`, `terminal_after_arrival`, `unknown` (bez rozpoznanej fazy). `seg` = id odcinka lub `null` (niedopasowana/niejednoznaczna). `flags`: m.in. `ambiguous`, `unmatched`, `no_delay`. `src` = indeksy w `sources`.
* `segments[].end`/`start` wskazują `obs` (indeks w `observations`); `start.kind`: `prev_end` lub `course_start`. `note` to polski opis braku (np. „przejechany w całości między obserwacjami”).
* `arrival` = wartość dojazdu do krańca albo `{"obs": null, "delay": null, "uncertain": "powód po polsku"}`; `null`, gdy wariant bez geometrii.
* Kursy wariantu nieobecnego w rozkładzie mają `segments: []` i `variant_status: "absent_in_gtfs"`, ale zachowują obserwacje.

## `data/quality.json`

Wolna struktura; przeglądarka pokazuje ją w panelu „Jakość i pochodzenie danych”:

```json
{
  "format": 1,
  "inputs": {"archive": "...", "gtfs": "...", "gtfs_feed_end_date": "20261125"},
  "range": {"from": "...", "to": "...", "skipped_days": [{"date": "2026-11-03", "reason": "..."}]},
  "counts": {"source_records": 0, "snapshots_read": 0, "snapshot_errors": 0, "provenance_gaps": 0,
             "raw_records": 0, "observations": 0, "conflicts": 0, "without_trip": 0},
  "lines": {"127": {"skipped_records": 0, "raw_skipped_records": 0, "courses": 0,
                    "variants_absent_in_gtfs": [{"variant": "32", "courses": 1, "observations": 10}],
                    "segment_coverage": {"4": {"passes": 100, "with_value": 80, "with_change": 70}}}},
  "notes": ["tekst po polsku", "..."]
}
```
