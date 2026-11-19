# Ciągłość przykładowych kursów 127 i 162

Rozpoznanie do rozmowy projektowej, wykonane 12 listopada 2026 r. Wszystkie godziny poniżej są w UTC; w badanym dniu czas lokalny Gdańska był o godzinę późniejszy. Badanie było tylko do odczytu.

## Zakres i pochodzenie

Odczytano 361 zapisów GPS z 10 listopada 2026 r., od slotu 11:00:00 do 13:00:00 włącznie, co 20 sekund, oraz wszystkie 361 odpowiadających im manifestów. Ścieżki są względne wobec katalogu archiwum:

- Pierwszy zapis: `snapshots/gps/2026-11-10/2026-11-10T11:00:00.000Z/cd570f0b-efbf-49d4-938c-377c77826902.json.gz`.
- Ostatni zapis: `snapshots/gps/2026-11-10/2026-11-10T13:00:00.000Z/31b56f2c-5895-48be-b30e-736fa078e8ea.json.gz`.
- Manifesty: `runs/2026-11-10/<slot>/<ten sam UUID>.json`.

Każdy manifest istnieje i ma status `complete`. Wpis GPS dopasowany po pełnym `key` wskazuje istniejący zapis, ma status `stored` i URL `https://ckan2.multimediagdansk.pl/gpsPositions?v=2`. Nie odczytywano zawartości departures ani GTFS-RT. Nie jest to audyt całego archiwum.

Zakresy czasu akwizycji: `fetchedAt` 11:00:00.000–13:00:00.000, `receivedAt` 11:00:01.152–13:00:00.353, `storedAt` 11:00:01.796–13:00:00.588. W danych GPS `lastUpdate` mieści się w 10:59:39–12:59:49. Czasy obserwacji w dalszych tabelach pochodzą z `generated`, czyli czasu zarejestrowania pozycji; nie ustalają osobnego czasu pomiaru opóźnienia.

## Cztery przypisania do kursów

Wszystkie podane czasy rozpoczęcia dotyczą 10 listopada. W obrębie każdego z czterech przypisań pola identyfikacji i nazwa kierunku były stabilne.

| Pojazd / linia / wariant / start / zadanie | Czas pierwszej–ostatniej obserwacji | Rekordy / różne czasy obserwacji | Opóźnienie pierwsze → ostatnie | Minimum / maksimum | Największa przerwa |
|---|---|---:|---|---|---:|
| 145985 / 127 / 41 / 11:00 / 127-02 | 10:59:37–12:05:01 | 197 / 177 | −29 → 729 s | −29 / 735 s | 45 s |
| 145728 / 127 / 202 / 11:37 / 127-01 | 11:37:30–12:56:55 | 239 / 212 | 18 → 0 s | −95 / 65 s | 45 s |
| 145725 / 162 / 22 / 11:45 / 162-05 | 11:44:42–12:24:28 | 120 / 107 | 0 → 0 s | 0 / 257 s | 46 s |
| 146270 / 162 / 22 / 11:25 / 162-04 | 11:24:16–12:01:00 | 111 / 99 | 0 → 0 s | −6 / 204 s | 45 s |

Powtórzenia czasu obserwacji nie zawierały zmian treści rekordu pojazdu. Wszystkie 1328 rekordów tych czterech pojazdów w całym badanym oknie, obejmujące również inne ich kursy, miały `gpsQuality=3`; czas slotu był od 1 do 32 sekund późniejszy od czasu pozycji.

## Zmiany przy krańcach tras

W kursie 127 / pojazd 145728 / start 11:37 zaobserwowano poniższą serię. Odległości dotyczą pomocniczej lokalizacji Oliwa PKP 04 ze statycznego rozkładu.

| Czas pozycji | Opóźnienie | Raportowana prędkość | Odległość od słupka |
|---|---:|---:|---:|
| 12:30:17 | 65 s | 35 km/h | 381 m |
| 12:30:36 | 59 s | 30 km/h | 212 m |
| 12:30:59 | 59 s | 30 km/h | 42 m |
| 12:31:18 | 0 s | 0 km/h | 37 m |
| 12:32:04 | 0 s | 0 km/h | 13 m |
| 12:56:55 | 0 s | 0 km/h | 14 m |

Między 12:33:09 a 12:56:55 występuje 65 różnych czasów obserwacji z zerową raportowaną prędkością i opóźnieniem, w odległości 7–17 m od słupka, nadal z tym samym przypisaniem do kursu. Nowy wariant 41 ze startem 13:00 pojawia się o 12:57:35. Mały rozrzut pozycji i zerowa raportowana prędkość są faktami; interpretacja jako postoju między kursami nie jest bezpośrednim polem danych.

W kursie 162 / pojazd 145725 / start 11:45 o 12:23:03 raportowano 257 s opóźnienia, 25 km/h i pozycję 87 m od Wrzeszcz PKP 06; o 12:23:25 — 0 s, 0 km/h i 55 m od słupka, przy tym samym przypisaniu do kursu. Zmiana ta nie ustala faktycznej punktualności przyjazdu.

Kurs 127 / pojazd 145985 / start 11:00 ma ostatnią obserwację o 12:05:01 z opóźnieniem 729 s i pozycją 41 m od krańca w Jasieniu. O 12:05:20 jest już przypisany do wariantu 202 ze startem 11:57 i opóźnieniem 497 s; nie jest to zmiana w obrębie tego samego kursu.

Wniosek projektowy: ostatnia wartość w długim przypisaniu do kursu może pochodzić z okresu po dojeździe do okolicy krańca. Również mediana wszystkich obserwacji tego przypisania na końcowym odcinku może zostać zdominowana przez późniejsze zera. Potrzebna jest jawna zasada prezentacji dojazdu i późniejszych obserwacji.

## Braki i przypisanie przestrzenne

- Pojazd 145985 podczas kolejnego kursu o 12:47:12 ma brak wariantu, czasu rozpoczęcia i nazwy kierunku oraz opóźnienie zero. O 12:47:34 wraca do poprzedniego przypisania z opóźnieniem 710 s. Pojedynczy brak przypisania nie dowodzi końca kursu.
- Pojazd 145725 jest nieobecny w 49 kolejnych zapisach ze slotów 12:25:00–12:41:00, a 146270 w 60 zapisach ze slotów 12:01:40–12:21:20. Są to braki pojazdów w poprawnie pozyskanych danych, nie luki pobierania całego źródła.
- Dla czterech kursów istnieją obserwacje w promieniu 200 m od każdego słupka pomocniczej trasy. W promieniu 100 m mieszczą się wszystkie z wyjątkiem Strzelnica 01 dla kursu 127 ze startem 11:37, gdzie najbliższa obserwacja jest oddalona o 144 m. Te promienie były wyłącznie diagnostyką, nie zatwierdzonym kryterium obsługi przystanku.
- Wybór najbliższego słupka bez uwzględnienia kolejności daje pozorne cofnięcia w przebiegu. Przypisanie do odcinków wymaga analizy kolejności obserwacji i przebiegu trasy.
- Diagnostyka z 12 XI sprawdziła rozważaną strefę `min(150 m, połowa odcinka)` przed przystankiem. Dla kursów 127 / 11:00, 127 / 11:37, 162 / 11:45 i 162 / 11:25 strefa zawierała obserwację na 31/32, 20/32, 14/19 i 12/19 odcinkach, a obie granice kolejnych odcinków — na 29/31, 13/31, 10/18 i 7/18. Rzutowanie było uproszczone (płaska projekcja, najbliższy punkt geometrii z ograniczeniem kolejności, do 75 m od trasy), bez potwierdzania postępu. Wynik uzasadnia [ADR 0005](adr/0005-wartosc-przy-koncu-odcinka.md).
- W ZIP sprawdzono sekwencje słupków i uporządkowane współrzędne geometrii wszystkich 16 par linia/wariant dla 127 i 162. Każda para ma jedną sekwencję i jedną geometrię, choć identyfikatorów geometrii jest od 2 do 4. Różne identyfikatory nie oznaczają tu różnych przebiegów.

## Zestaw kursów do weryfikacji

Uzupełnienie z 12 listopada 2026 r. Okno z 10 XI zawiera tylko jeden kierunek linii 162, dlatego w ten sam sposób odczytano 361 zapisów GPS z 9 listopada, ze slotów 11:00:00–13:00:00 UTC. Razem z oknem z 10 XI jest to 722 zapisy GPS.

- Pierwszy zapis: `snapshots/gps/2026-11-09/2026-11-09T11:00:00.000Z/8ca36e9e-159c-42ae-b22a-1069a7b903e9.json.gz`.
- Ostatni zapis: `snapshots/gps/2026-11-09/2026-11-09T13:00:00.000Z/859b73be-b7f2-4ffd-9f77-8df7785d080e.json.gz`.
- Każdy z 361 manifestów ma status `complete`; wpis GPS dopasowany po `key` ma status `stored` i ten sam URL co w oknie z 10 XI.

Kurs identyfikują linia, zadanie przewozowe i rozkładowy czas rozpoczęcia. Kierunek to `direction_id` wariantu w pomocniczym GTFS. Zestaw obejmuje cztery kursy opisane wyżej oraz pięć innych kursów, których wszystkie obserwacje mieszczą się w oknie:

| Dzień | Linia / wariant / kierunek | Start | Zadanie | Pojazd | Pierwsza–ostatnia obserwacja | Różne czasy obserwacji |
|---|---|---|---|---|---|---:|
| 9 XI | 127 / 41 / 0 → Jasień PKM | 11:20 | 127-03 | 202 | 11:17:20–12:18:09 | 166 |
| 9 XI | 127 / 202 / 1 → Oliwa PKP | 11:17 | 127-07 | 145980 | 11:17:23–12:38:17 | 221 |
| 9 XI | 162 / 71 / 0 → Orunia Górna | 11:04 | 162-05 | 212 | 11:01:24–11:44:06 | 114 |
| 9 XI | 162 / 22 / 1 → Wrzeszcz PKP | 11:05 | 162-03 | 146270 | 11:05:15–11:46:31 | 112 |
| 10 XI | 127 / 41 / 0 → Jasień PKM | 11:00 | 127-02 | 145985 | 10:59:37–12:05:01 | 177 |
| 10 XI | 127 / 202 / 1 → Oliwa PKP | 11:37 | 127-01 | 145728 | 11:37:30–12:56:55 | 212 |
| 10 XI | 162 / 71 / 0 → Orunia Górna | 11:24 | 162-01 | 191 | 11:20:43–11:59:27 | 105 |
| 10 XI | 162 / 22 / 1 → Wrzeszcz PKP | 11:25 | 162-04 | 146270 | 11:24:16–12:01:00 | 99 |
| 10 XI | 162 / 22 / 1 → Wrzeszcz PKP | 11:45 | 162-05 | 145725 | 11:44:42–12:24:28 | 107 |

Pojazd 191 kończy kurs ze startem 11:24 obserwacją o 11:59:27, ma rekord bez przypisania o 11:59:47, opisany w [rozpoznaniu archiwum](rozpoznanie-archiwum.md), i od 12:00:12 realizuje kurs 162 / 22 ze startem 12:00. Jest to przykład przejścia między kursami z chwilowym brakiem przypisania.

Najkrótsze odcinki wzdłuż pomocniczej geometrii występują w linii 127: Oliwa PKP 04 → Oliwa PKP 02 ma 58 m (warianty 41 i 301), a Oliwa PKP 01 → Oliwa PKP 04 ma 101 m (warianty 102, 202 i 212). Linia 162 nie ma odcinków krótszych niż 150 m.

## Początek kursów w tygodniu 4–10 listopada

Odczytano wszystkie obserwacje linii 127 i 162 z lokalnych dób 4–10 XI, zdeduplikowane po pojeździe i `generated`. Spośród 1938 kursów 201 ma wariant nieobecny w pomocniczym GTFS. Dla pozostałych 1737 odległości liczono w linii prostej do pierwszego słupka wariantu. Postój oznacza zerową raportowaną prędkość w promieniu 150 m od tego słupka.

- 1632 kursy mają pierwszą obserwację w promieniu 150 m od pierwszego słupka (mediana 43 m), a 105 — dalej.
- W 1043 kursach po postoju następuje ruch, w 585 pierwsza obserwacja już jest w ruchu, a w 4 pojazd nie rusza przed końcem przypisania.
- Postój z nowym przypisaniem trwa w medianie 87 s (90. percentyl: 191 s). Odstęp między ostatnią obserwacją postoju a pierwszą w ruchu ma medianę 21 s i tylko w 6 kursach przekracza 60 s.
- Ostatnia obserwacja postoju raportuje zero w 481 kursach, pierwsza obserwacja w ruchu — w 161. Różnica „pierwsza w ruchu minus ostatnia w postoju” ma medianę 11 s (10. percentyl: −4 s, 90.: 26 s) i przekracza 60 s w 31 kursach.
- W 121 kursach, które ruszają co najmniej 120 s po czasie rozkładowym, obie wartości śledzą opóźnienie odjazdu: różnica nie przekracza 60 s w odpowiednio 118 i 117 przypadkach.

## Ograniczenia

Badanie nie sprawdza historycznej zgodności geometrii przez cały tydzień ani skuteczności gotowego algorytmu przypisania do odcinków. Bliskość przystanku nie dowodzi obsługi pasażerów ani dokładnego czasu przyjazdu. Źródło nie podaje przyczyny zmian opóźnienia przy krańcach. Statyczny ZIP pozostaje wskazówką; jego URL pozyskania i czas pobrania są nieudokumentowane.
