# ztm-viz – wizualizacja opóźnień ZTM Gdańsk

Zestaw skryptów w Pythonie, który z lokalnego archiwum GPS tworzy statyczny, interaktywny raport HTML (mapa + wykres
opóźnienia wzdłuż trasy) dla wskazanych linii. Archiwum jest tylko czytane; wyniki trafiają do osobnego katalogu.

Podstawa: [założenia](../docs/zalozenia-wizualizacji.md), [plan](../docs/plans/0001-wizualizacja-opoznien-ztm.md),
[ADR 0001–0005](../docs/adr), [słownik](../GLOSSARY.md). Format danych raportu: [FORMAT.md](FORMAT.md).

## Wymagania i instalacja

* [uv](https://docs.astral.sh/uv/) – sam pobierze Pythona 3.15 (`.python-version`); zależności są w `uv.lock`.
* Node.js ≥ 20 tylko do testów przeglądarkowych (`web-tests/`).

```bash
cd /workspace/src
uv sync
```

## Uruchamianie

```bash
# 1. przygotowanie zbioru (wszystkie pełne doby lokalne; linie są wymaganym parametrem)
uv run ztm-viz prepare --archive /workspace --gtfs /workspace/gtfsgoogle.zip \
  --lines 127 162 --out /workspace/outputs/ztm/dataset.sqlite
# opcjonalnie: --from 2026-11-05 --to 2026-11-07 zawęża zakres do wskazanych pełnych dób

# 2. raport statyczny (nie czyta już surowego archiwum)
uv run ztm-viz report --dataset /workspace/outputs/ztm/dataset.sqlite --out /workspace/outputs/ztm/report

# 3. lokalny podgląd
uv run ztm-viz serve --report /workspace/outputs/ztm/report --port 8000   # http://127.0.0.1:8000/
```

* `--lines` przyjmuje jedną lub więcej publicznych nazw linii (`routeShortName`, także z literami, np. `N8`, `T8`).
  Inne linie wymagają tylko zmiany tego parametru.
* `prepare` zapisuje `dataset.sqlite` i `dataset.quality.json` (podsumowanie jakości: zakres dób, doby pominięte,
  liczniki zapisów, konfliktów, rekordów bez kursu, warianty nieobecne w rozkładzie, pokrycie odcinków i diagnostyka
  parametrów). Pliki powstają atomowo – przerwane przetwarzanie nie zastępuje poprzedniego wyniku.
* Katalog raportu jest samodzielny i działa pod dowolnym serwerem plików statycznych, także w podkatalogu adresu
  (ścieżki względne, stan wyboru w fragmencie `#…`). Przez `file://` pokazuje komunikat, że wymaga HTTP. Podkład
  OpenStreetMap jest pobierany z internetu; jego brak nie blokuje tras ani wykresu.

## Jak liczone są wartości (skrót; pełne reguły w planie)

* Obserwacja = pojazd + `generated`; powtórzenia są scalane (zachowane powiązania ze wszystkimi zapisami źródłowymi).
  Wersja z przypisaniem do kursu i wersja bez żadnego przypisania nie są konfliktem; różne przypisania lub pomiary są.
* Kurs = linia + zadanie przewozowe + archiwalny czas rozpoczęcia; ciągłe fragmenty dzielą zmiana pojazdu lub
  wariantu, przerwa > 90 s i konflikt obserwacji.
* Dopasowanie do trasy GTFS jest kolejnościowe (Viterbi po konkurujących rzutowaniach), z jawnymi odmowami
  (`variant_mismatch`, obserwacje `ambiguous`/`unmatched`). Wariant spoza GTFS nie daje wartości.
* Wartość przy końcu odcinka = ostatnia obserwacja przed granicą przystanku (25 m przed słupkiem), jeśli następna
  jest już za granicą w ≤ 60 s (ADR 0005). Początek kursu i dojazd do krańca: ADR 0003/0005.
* Mediana po kursach (równa waga), zmiana liczona w kursie. Kolory: ≤0 zielony, >0–300 s pomarańczowy, >300 s czerwony.

### Decyzja z diagnostyki etapu 2 (odstępstwo od brzmienia planu)

Plan: „oznaką ruchu jest prędkość lub przesunięcie pozycji”. Na tygodniu 127/162 przy progu przesunięcia 20 m aż 81%
rozstrzygniętych dojazdów (996 z 1231) miało opóźnienie 0 – czyli wartość z obserwacji, w której źródło zeruje
opóźnienie przy krańcu (np. 257 s → 0 s przy prędkości 0 i przesunięciu 32 m). Dla 40 m: 73%; przy samej raportowanej
prędkości: 45% (631 z 1412), a rozstrzygniętych dojazdów jest więcej. Dlatego **o ruchu decyduje raportowana prędkość;
przesunięcie pozycji (`move_shift_m`, 20 m) jest używane tylko, gdy prędkości brak.** Wymaga zatwierdzenia.

## Testy

```bash
uv run pytest                       # import, kursy/odcinki, eksport (syntetyczne archiwum)
cd web-tests && npm install && npm test          # node --test: statystyki w aggregate.js
node make-fixture.js && node e2e.js              # Playwright (HTTP pod podkatalogiem, 400 px, brak kafelków)
node smoke-real.js /workspace/outputs/ztm/report # przejście po prawdziwym raporcie
```
Pierwsze uruchomienie Playwrighta: `npx playwright install chromium` (oraz biblioteki systemowe, jeśli brakuje).

## Pomiary (środowisko: kontener Linux aarch64, uv Python 3.15.2; bez pobierania kafelków)

| Zakres | Czas / rozmiar |
|---|---|
| `prepare`, 127+162, tydzień (30 190 zapisów GPS, 231 053 obserwacji) | ok. 80 s |
| `prepare`, 8+N8 | ok. 70 s |
| `report`, 127+162 (1938 kursów) | ok. 4 s; 157 MB (1968 plików), z czego pakiety dób 1,7 MB, szczegóły kursów 153 MB |
| pierwszy widok (HTTP lokalny, Chromium headless) | ok. 0,6 s |
| szczegóły odcinka / otwarcie kursu / zmiana filtra godzin | ok. 0,1 s / 0,1 s / 0,3 s |

## Ograniczenia

* Konflikty wersji obserwacji są wykrywane tylko wśród rekordów wskazanych linii.
* Obserwacje z `gpsQuality` 0–1 (w tygodniu 127/162 ok. 89) są używane bez osobnego oznaczenia.
* Linie, dla których żaden wariant nie ma geometrii w GTFS, nie są oferowane w raporcie (`lines_without_timetable` w manifeście i panel jakości).
* Nie są zweryfikowane trafnością: progi dopasowania (75 m, 30 m, 90 s, 60 s, 25 m, 150 m) to początkowe założenia
  planu; diagnostyka pokrycia jest w `dataset.quality.json` (`segment_coverage`).
* Rozkład GTFS to wskazówka niezależna od dat kalendarza; brak zgodności trasy nie uprawnia do dopisywania przejazdów.
* Linie 8 i N8 sprawdzono tylko przeglądem próbnego uruchomienia – to nie jest pełna weryfikacja tych linii.
