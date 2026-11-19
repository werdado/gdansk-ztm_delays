# Rozpoznanie danych dla linii 127 i 162

Rozpoznanie do rozmowy projektowej, wykonane 12 listopada 2026 r. Obejmuje trzy pojedyncze zapisy GPS oraz pomocniczy statyczny rozkład; nie sprawdzono ciągłości całych kursów ani kompletności archiwum. Interpretację pól oparto na lokalnej dokumentacji GPS i GTFS.

## Pochodzenie próbek

Ścieżki poniżej są względne wobec katalogu archiwum. Każdy manifest ma status `complete`, a odpowiadający mu wpis źródła GPS ma status `stored`, adres `https://ckan2.multimediagdansk.pl/gpsPositions?v=2` i klucz wskazujący na istniejący zapis.

| Planowany moment pobrania, UTC | Manifest | Zapis GPS |
|---|---|---|
| 2026-11-03 17:14:14.289 | `runs/2026-11-03/2026-11-03T17:14:14.289Z/5abd6737-9498-480c-bb92-1c504aeed091.json` | `snapshots/gps/2026-11-03/2026-11-03T17:14:14.289Z/5abd6737-9498-480c-bb92-1c504aeed091.json.gz` |
| 2026-11-10 12:00:00 | `runs/2026-11-10/2026-11-10T12:00:00.000Z/c2bc89ee-08b3-4a9c-80dc-de109bd52701.json` | `snapshots/gps/2026-11-10/2026-11-10T12:00:00.000Z/c2bc89ee-08b3-4a9c-80dc-de109bd52701.json.gz` |
| 2026-11-11 07:36:20 | `runs/2026-11-11/2026-11-11T07:36:20.000Z/fb3a7191-c98f-4326-882b-0bb4dc0f886a.json` | `snapshots/gps/2026-11-11/2026-11-11T07:36:20.000Z/fb3a7191-c98f-4326-882b-0bb4dc0f886a.json.gz` |

Godziny poniżej są w UTC, w dniu wskazanym w pierwszej kolumnie. `generated` oznacza według dokumentacji czas zarejestrowania pozycji, a nie czas pobrania.

| Dzień | `fetchedAt` | `receivedAt` | `storedAt` | `lastUpdate` wewnątrz GPS |
|---|---|---|---|---|
| 3 XI | 17:14:15.273 | 17:14:18.778 | 17:14:19.388 | 17:14:00 |
| 10 XI | 12:00:00.000 | 12:00:01.315 | 12:00:02.049 | 11:59:49 |
| 11 XI | 07:36:20.000 | 07:36:20.185 | 07:36:20.353 | 07:36:04 |

## Obserwacje istotne dla projektu

- W próbach z 3, 10 i 11 XI są odpowiednio 6, 7 i 4 pojazdy linii 127 oraz 4, 4 i 2 pojazdy linii 162.
- W zapisie z 10 XI pojazd 191 linii 162, zadanie `162-01`, ma `tripId=null`, `scheduledTripStartTime=null`, pusty `headsign` i `delay=0`; czas pozycji to `2026-11-10T11:59:47Z`. Zero bez rozpoznanego kursu nie potwierdza nadrobienia opóźnienia.
- Poza tym przypadkiem pola identyfikacji kursu były wypełnione w badanych rekordach obu linii. Wynik dotyczy jedynie tych 27 obserwacji.
- GPS nie podaje odrębnego czasu wyznaczenia opóźnienia. Wspólne wystąpienie pozycji i opóźnienia w rekordzie nie dowodzi ich ścisłej synchronizacji.
- Numer wariantu, pojazd lub zadanie przewozowe samodzielnie nie wystarczają do rozróżnienia kolejnych kursów.

## Pomocnicze wskazówki statycznego rozkładu

Sprawdzono `routes.txt`, `trips.txt`, `stops.txt` i krańcowe wpisy wybranych kursów w `stop_times.txt` w `gtfsgoogle.zip`. Poniższa tabela nie ustala historycznie obowiązującego przebiegu trasy.

| Linia | Wariant | Początek → koniec | Liczba słupków |
|---|---|---|---|
| 127 | 202 | Jasień PKM 01 → Oliwa PKP 04 | 33 |
| 127 | 41 | Oliwa PKP 04 → Jasień PKM 01 | 33 |
| 162 | 22 | Orunia Górna 01 → Wrzeszcz PKP 06 | 20 |
| 162 | 71 | Wrzeszcz PKP 06 → Orunia Górna 01 | 23 |
| 162 | 11 | Wrzeszcz PKP 04 → Orunia Górna 01 | 22 |

W ZIP znaleziono 11 numerów wariantów linii 127 i 5 linii 162, w tym przejazdy skrócone. Dla jednego wariantu mogą występować różne geometrie; ich zgodności nie sprawdzono. Nazwane kierunki przejazdu nie są tym samym co kierunek geograficzny pojazdu z rekordu GPS.

## Przegląd archiwum i lokalnych dób 4–10 listopada

Uzupełnienie z 12 listopada 2026 r., tylko do odczytu.

**Manifesty w całym archiwum (3–11 XI UTC):** 32 818 manifestów — 32 733 `complete`, 65 `partial`, 20 `skipped` z `reason: slot_expired`. Każdy z 32 773 zapisów GPS ma w manifeście wpis `stored` o tym samym `key`, a każdy taki wpis wskazuje istniejący plik. Nie znaleziono zapisów bez manifestu.

**Doby lokalne 4–10 XI:** 30 190 zapisów GPS ze slotów od `2026-11-03T23:00:00.000Z` do `2026-11-10T22:59:40.000Z`. Wszystkie dały się rozpakować i odczytać. Zawierają 6 066 346 rekordów pojazdów i 5 514 792 różne pary pojazd–`generated`. Pierwsza i ostatnia doba archiwum, 3 i 11 XI, są niepełne.

**Różne treści dla tej samej pary pojazd–`generated`:** 7408 powtórzeń we wszystkich liniach.
- 7176 różni się wyłącznie polami `tripId`, `scheduledTripStartTime` i `headsign`.
- 123 zmienia także `routeId` i `vehicleService`, a 54 tylko pozycję.
- 6 dotyczy pola `delay`.

Dla pojazdów linii 127 i 162 takich par jest 26 na 231 053. W każdej najpierw występuje rekord z przypisaniem do kursu, a później ta sama pozycja i to samo opóźnienie bez przypisania.

**Identyfikatory:**
- `tripId` w GPS jest numerem wariantu i jest jednoznaczny tylko w obrębie linii; np. wariant 22 występuje w 28 liniach.
- Prefiks `vehicleService` to dopełniony zerami `routeId`, a nie `routeShortName` (M32 → `332`, T8 → `808`).
- Linia 171 występuje w GPS z `routeId` 171 i 10171, a w GTFS tylko jako 171. Pozostałe 92 linie mają zgodne identyfikatory.
- Wartości `lat` i `lon` są stopniami geograficznymi (np. 54,342 i 18,579), mimo że opis źródła wymienia EPSG:3857.

**Pokrycie pomocniczym GTFS:**
- W GPS występuje 861 par linia–wariant; 330 z nich brakuje w GTFS. Obejmują 1,80% obserwacji z przypisaniem, a przy łączeniu po `routeShortName` zamiast `routeId` — 1,61%.
- W linii 127 brakuje wariantów 32, 52, 71, 91, 112, 121 i 312, czyli 1128 obserwacji (0,8%). W linii 162 brakuje wariantów 51, 61, 82 i 121, czyli 1031 obserwacji (1,3%).
- Każda z 539 par `route_id`–wariant w ZIP ma jedną sekwencję słupków, jedną geometrię (po zaokrągleniu do 5 miejsc), jeden `direction_id` i jeden `trip_headsign`, choć 524 pary mają więcej niż jeden `shape_id`.
- Kalendarz ZIP obejmuje 11–25 XI 2026 r. (`feed_end_date` 20261125), a więc prawie w całości późniejszy okres niż archiwum.

## Granice rozpoznania

- Z pojedynczych zapisów nie można ustalić przebiegu opóźnienia ani tego, czy zostało nadrobione do końca kursu.
- Nie sprawdzono pokrycia krańców tras, zmian przypisania pojazdu, ciągłości identyfikatorów ani zgodności historycznych przejazdów z geometrią pomocniczą.
- Manifesty i zapisy są dopasowane tylko dla opisanych próbek. Nie jest to audyt kompletności całego archiwum.
- Pochodzenie i czas pobrania statycznego ZIP pozostają nieudokumentowane. Daty jego kalendarza nie ograniczają użycia jako wskazówki, zgodnie z [ADR 0001](adr/0001-archiwum-jako-zrodlo-prawdy.md).
