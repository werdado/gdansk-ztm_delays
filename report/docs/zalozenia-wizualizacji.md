# Założenia wizualizacji komunikacji miejskiej

Status: zatwierdzona przez użytkownika 12 listopada 2026 r., po potwierdzeniu całości w Q16.

Specyfikacja wynika z odpowiedzi na Q1–Q15 rozmowy projektowej i stanowi uzgodnioną podstawę planu implementacji. Kryteria odbioru opisują oczekiwane zachowanie przyszłych skryptów; kwestie wymagające sprawdzenia na pełnym archiwum pozostają jawnie wymienione na końcu dokumentu.

## Ustalone wymagania

- Narzędzia mają postać zestawu skryptów w Pythonie.
- Wyniki, opisy i dalsza dokumentacja projektowa mają być po polsku.
- Wizualizacje mają być zrozumiałe dla ogółu społeczeństwa.
- Przykładem oczekiwanego rezultatu jest pokazanie opóźnienia linii 127 i 162 na całej długości: gdzie się pojawiało, gdzie malało i czy zostało ostatecznie nadrobione. Te linie są przypadkami odniesienia, nie ustalonym ograniczeniem wszystkich przyszłych skryptów.
- Punktem wejścia jest obraz zbiorczy dla wybranego przedziału czasowego, np. godziny. Odbiorca musi móc przejść z niego do danych pojedynczego kursu; dane na poziomie kursu są wymagane.
- Zakres obejmuje cały dostępny okres archiwum, określony w rozmowie jako tydzień. Przetwarzane są pełne doby czasu lokalnego; niepełne doby na krańcach archiwum są pomijane, więc dla obecnego archiwum zakres to 4–10 listopada 2026 r. Domyślny widok ma pokazywać ten cały okres, z możliwością zawężenia czasu.
- Głównym wynikiem jest interaktywny raport HTML otwierany w przeglądarce, z mapą i wykresem opóźnienia wzdłuż trasy. Raport jest katalogiem plików statycznych udostępnianym przez HTTP. Uzasadnienie: [ADR 0004](adr/0004-statyczny-raport-przez-http.md).
- Kolor obrazu zbiorczego pokazuje medianę opóźnienia, z równą wagą każdego kursu. Szczegóły wskazanego miejsca zawierają również największe opóźnienie i liczbę uwzględnionych kursów. Uzasadnienie: [ADR 0002](adr/0002-agregacja-opoznien-po-kursach.md).
- Wartością reprezentującą pojedynczy kurs na odcinku jest raportowane opóźnienie przy końcu tego odcinka. Obok poziomu opóźnienia pokazujemy jego zmianę względem początku odcinka: dodatnia oznacza wzrost, ujemna — zmniejszenie.
- Zmianę opóźnienia liczymy najpierw wewnątrz każdego kursu, a dopiero potem jej medianę po kursach. Nie wyznaczamy zmiany przez odejmowanie median dwóch różnych zbiorów kursów.
- Kolory oznaczają: zielony — brak dodatniego opóźnienia; pomarańczowy — opóźnienie większe od zera i nieprzekraczające 5 minut; czerwony — ponad 5 minut. Szary oznacza brak danych. Dokładna wartość jest dostępna liczbowo; wartości ujemne opisujemy jako „przed czasem”.
- Filtr godzin obejmuje obserwacje z tej pory we wszystkich zaznaczonych dniach, według czasu lokalnego Gdańska. Zakres godzin przechodzący przez północ dotyczy nocy rozpoczętej w zaznaczonym dniu. Fragment kursu rozpoczętego przed wybranym przedziałem jest uwzględniany, jeżeli ma obserwacje wewnątrz przedziału. Po przejściu do pojedynczego kursu pokazujemy jego cały dostępny przebieg.
- Podstawową jednostką przestrzenną obrazu zbiorczego jest odcinek między przystankami. Wyniki liczymy oddzielnie dla każdej linii i kierunku; różne warianty łączymy tylko na zgodnych odcinkach. Rozkład pomaga nazwać odcinki, archiwum określa obserwowany przejazd.
- Dane z dojazdu do końca trasy pokazujemy oddzielnie od późniejszych obserwacji przy krańcu. Późniejsze zero pozostaje widoczne, ale nie zastępuje wartości z dojazdu; niepewne rozdzielenie jest jawnie opisane. Uzasadnienie: [ADR 0003](adr/0003-dojazd-a-obserwacje-przy-krancu.md).
- Wiarygodnie rozpoznane fragmenty niepełnych kursów uczestniczą w podsumowaniu. W widoku pojedynczego kursu brakujące odcinki pozostają szare; w obrazie zbiorczym szary oznacza brak kwalifikujących się wartości dla danego odcinka i filtra.
- Rekordy bez rozpoznanego kursu nie uczestniczą w medianie po kursach; raport podaje liczbę pominiętych rekordów. Brakującego przebiegu nie uzupełniamy zerowym opóźnieniem.
- Pierwszy raport obejmuje linie 127 i 162; skrypty mają pozwalać później wybrać inne linie.
- Dostęp do internetu podczas oglądania raportu jest dopuszczalny, np. dla podkładu mapy. Dane transportowe pochodzą z lokalnego archiwum; pełne działanie bez internetu nie jest wymaganiem pierwszej wersji.
- Archiwum jest źródłem prawdy; statyczny rozkład pozostaje wskazówką niezależnie od dat. Uzasadnienie i konsekwencje: [ADR 0001](adr/0001-archiwum-jako-zrodlo-prawdy.md).
- Surowe zapisy pozostają zachowane; dane przekształcone i wyniki wymagają osobnej lokalizacji zgodnie z instrukcjami archiwum.

## Ustalenia wynikające z dokumentacji źródeł

- Raportowane opóźnienie, pozycja GPS i prognoza odjazdu są odrębnymi informacjami. Ich znaczenia opisuje [słownik](../GLOSSARY.md).
- Dokumentacja GPS określa czas zarejestrowania pozycji, ale nie opisuje odrębnego znacznika czasu pomiaru opóźnienia. Przypisanie zmiany opóźnienia do konkretnego miejsca będzie wymagało uwzględnienia tej granicy dokładności.
- Kolejne pobrania mogą powtarzać obserwację z pamięci podręcznej źródła.
- Brak obserwacji oznacza niewiedzę. W szczególności zniknięcie pojazdu z danych nie potwierdza zakończenia kursu ani nadrobienia opóźnienia.

## Reguły wynikające z połączenia ustaleń

- Filtr czasu dotyczy obserwacji, a nie godziny rozpoczęcia kursu. Wartość końcowa odcinka musi pochodzić z wybranego zakresu; zmiana na odcinku wymaga kwalifikującej się pary obserwacji jego początku i końca. Jeśli filtr wycina początek, można pokazać poziom opóźnienia przy końcu, ale zmiana w tym zakresie pozostaje nieznana. Pełny profil kursu jest dostępny po przejściu do jego widoku.
- Liczba kursów z rozpoznanym opóźnieniem przy końcu odcinka może być większa niż liczba kursów pozwalających obliczyć zmianę. Raport rozróżnia te liczebności.
- Maksimum i mediana w opisie zbiorczym dotyczą tych samych wartości reprezentujących kursy. Powtarzane zapisy tej samej obserwacji nie zwiększają liczby kursów ani ich wagi.
- Opóźnienie przy końcu odcinka jest informacją raportowaną w okolicy jego końca, a nie pomiarem dokładnego czasu przyjazdu na przystanek. Dokładność przypisania zależy od jakości obserwacji.
- Kolor klasyfikuje wartość przed zaokrągleniem tekstu. Odbiorca może odczytać wartość liczbową i znaczenie kategorii; sam kolor nie jest jedynym nośnikiem informacji.
- Pokazanie rozkładu pomocniczego poza datami jego kalendarza jest dozwolone. Brak zgodności jego trasy z obserwacjami nie uprawnia do dopisania przejazdu ani opóźnienia.

## Przebieg korzystania z raportu

1. Odbiorca otwiera raport HTML po polsku i widzi podsumowanie całego dostępnego okresu, z liniami 127 i 162 oraz rozdzielonymi kierunkami.
2. Wybiera linię, kierunek, dni oraz porę dnia. Mapa i wykres odpowiadają temu samemu zakresowi; ekran pokazuje aktywny filtr i liczbę kursów.
3. Wskazuje odcinek i odczytuje typowe opóźnienie, maksimum, zmianę oraz liczebność danych. Może przejść do kursów będących podstawą tego wyniku.
4. Wybiera kurs i ogląda jego cały dostępny przebieg, z poziomem i zmianą opóźnienia, lukami oraz oddzielnymi obserwacjami przy krańcu. Widok oznacza, że prezentuje pełny kurs, również poza wcześniejszym filtrem czasu.
5. Wraca do podsumowania z zachowanymi filtrami.

## Kryteria odbioru pierwszego raportu

Poniższe kryteria opisują oczekiwane zachowanie, nie wyniki już wykonanych testów.

| Przypadek | Oczekiwany rezultat |
|---|---|
| Otwarcie raportu | Polski interfejs, mapa i wykres dla całego dostępnego okresu; możliwość wyboru 127 lub 162 oraz kierunku. |
| Wybranie godziny 8:00–9:00 w kilku dniach | Uwzględnione obserwacje z tej godziny czasu lokalnego w zaznaczonych dniach, także z kursów rozpoczętych wcześniej. |
| Przejście z odcinka do kursu | Można wskazać kurs leżący u podstaw wyniku i obejrzeć cały jego dostępny profil; powrót zachowuje filtry. |
| Kurs z opóźnieniem 2 min na początku i 5 min na końcu odcinka | Poziom 5 min i wzrost 3 min. Przy spadku z 8 do 5 min: poziom 5 min i zmiana −3 min. |
| Powtórzenie tej samej obserwacji w kolejnych zapisach | Wynik, liczba kursów i ich wagi nie zmieniają się. |
| Opóźnienia −30 s, 0 s, 300 s, 301 s | Odpowiednio: zielony z opisem „przed czasem”, zielony, pomarańczowy, czerwony; wartości liczbowe dostępne. |
| Odcinek bez kwalifikujących się danych | Szary z opisem braku danych, bez dopisanego zera. |
| Znany koniec odcinka, nieznany początek | Poziom opóźnienia dostępny; zmiana nieznana. Liczebności poziomu i zmiany są rozróżnione. |
| Kurs częściowo obserwowany | Rozpoznane odcinki uczestniczą w podsumowaniu; luki są widoczne w kursie. |
| Rekord bez rozpoznanego kursu | Nie uczestniczy w medianie po kursach; liczba pominiętych rekordów jest dostępna. |
| Zero raportowane po dojeździe w okolice krańca | Nie zastępuje wartości z dojazdu; późniejsze obserwacje są dostępne oddzielnie. Niepewny dojazd jest oznaczony. |
| Niezgodność wariantu pomocniczego z przejazdem | Raport nie przypisuje automatycznie obserwacji do niepotwierdzonego odcinka. Pokazuje ograniczenie pokrycia. |
| Weryfikacja wyniku | Można prześledzić wartość z raportu przez kurs i obserwacje do zapisów źródłowych oraz dopasowanych manifestów; zakres i luki pochodzenia danych są opisane. |

## Odpowiedzialności i założenia do planu wykonania

W tym katalogu nie ma istniejących skryptów wizualizacji. Poniższy podział porządkuje odpowiedzialności przyszłego rozwiązania; nie przesądza o bibliotekach ani podziale na pliki.

| Odpowiedzialność | Właściciel i cykl życia |
|---|---|
| Pozyskanie surowych danych | Zewnętrzny kolektor; skrypty wizualizacji odczytują istniejące archiwum i go nie zmieniają. |
| Przygotowanie danych | Skrypty uruchamiane przez autora raportu: sprawdzają pochodzenie, rozpoznają obserwacje i kursy, dopasowują przebieg oraz zapisują pochodne wyniki w osobnej lokalizacji. |
| Obliczenia i reguły jakości | Proces przygotowania i generowania raportu odpowiada za zgodność wartości indywidualnych, agregatów i liczebności; zachowuje możliwość prześledzenia pochodzenia. |
| Prezentacja i filtry | Raport przeglądarkowy przechowuje stan bieżącego wyboru odbiorcy; zmiana filtrów nie modyfikuje archiwum. |
| Aktualizacja danych raportu | Autor ponownie uruchamia skrypty dla wybranego wejścia; odbiorca korzysta z wygenerowanego wyniku. |

Założenie wykonawcze: podstawą pierwszego profilu opóźnień są archiwalne rekordy GPS, które zawierają pozycję, raportowane opóźnienie i przypisanie do kursu. Prognozy odjazdów są inną wielkością; ewentualne użycie pozostałych archiwalnych źródeł do rozpoznawania kursów wymaga jawnego sprawdzenia zgodności identyfikatorów i czasu. Nie scala się automatycznie różnych miar opóźnienia.

Raport ma być czytelny także na małym ekranie, z wartościami liczbowymi i opisami obok kolorów. Odbiorca nie potrzebuje Pythona do oglądania wyniku. Konkretne biblioteki, sposób pakowania HTML, limity czasu generowania i wielkości wyniku wymagają doboru oraz pomiaru na rzeczywistym archiwum; nie są ustalonymi przez użytkownika limitami.

## Zakres wyłączony z pierwszej wersji

Pierwsza wersja opisuje archiwalne opóźnienia. Nie obejmuje zbierania bieżących danych, oceniania trafności prognoz odjazdów, publikacji na hostingu ani pełnego działania mapy bez internetu. Nie obiecuje ustalenia dokładnych rzeczywistych czasów przyjazdu lub przyczyny opóźnienia na podstawie samego pola opóźnienia. Ewentualne rozszerzenia wymagają odrębnego ustalenia zakresu.

## Otwarte kwestie do sprawdzenia w danych

Wstępne próbki, ich pochodzenie i ograniczenia zapisano w [rozpoznaniu archiwum](rozpoznanie-archiwum.md). Obecność obu linii jest potwierdzona w próbkach; pokrycie kursów w całym archiwum pozostaje do sprawdzenia.

[Rozpoznanie czterech kursów](rozpoznanie-kursow.md) obejmuje dodatkowo 361 kolejnych zapisów GPS z dwóch godzin 10 listopada. Pokazuje powtarzane obserwacje, chwilową utratę przypisania, zmiany opóźnienia przy krańcach oraz potrzebę uwzględnienia kolejności przejazdu podczas dopasowania do przystanków. Nie rozstrzyga jakości całego tygodnia ani skuteczności przyszłego algorytmu.

- Stabilność rozpoznawania kursów przez cały tydzień, w tym chwilowe braki przypisania, zmiany pojazdu i wariantu. Odpowiedzialność: przygotowanie danych; niejednoznaczności pozostają jawne.
- Pokrycie początku, środka i końca kursów oraz wiarygodność rozdzielenia dojazdu i późniejszych obserwacji przy krańcu. Odpowiedzialność: reguły jakości, sprawdzane na przebiegach źródłowych.
- Dopasowanie pomocniczej geometrii do historycznych obserwacji z uwzględnieniem kolejności; progi odległości i dopuszczalnych przerw wymagają weryfikacji. Odpowiedzialność: przygotowanie danych; same diagnostyczne promienie z rozpoznania nie są gotowym algorytmem.
- Rozmiar danych raportu, czas przygotowania i sprawność interakcji w przeglądarce. Odpowiedzialność: generator i prezentacja; potrzebny pomiar całego zakresu 127/162.

Te kwestie są jawnymi zadaniami weryfikacyjnymi przyszłej implementacji, a nie powodami do uznania nieobserwowanych przejazdów za punktualne. Szczegółowy plan nie powinien z góry zakładać skuteczności niezweryfikowanego dopasowania tras i krańców.
