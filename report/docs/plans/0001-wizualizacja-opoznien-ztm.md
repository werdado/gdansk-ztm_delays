# Plan implementacji wizualizacji opóźnień ZTM

## 1. Cel i architektura

**Cel:** zestaw skryptów w Pythonie generujący polski raport dla jednej lub wielu linii wskazanych w konfiguracji uruchomienia: od podsumowania całego archiwum, przez wybrany przedział czasu, do pojedynczego kursu. Linie 127 i 162 są przykładowym zestawem do weryfikacji, a nie stałym zakresem działania programu.

**Podstawa:** [zatwierdzona specyfikacja](../zalozenia-wizualizacji.md), [słownik](../../GLOSSARY.md), ADR 0001–0005 oraz rozpoznanie [archiwum](../rozpoznanie-archiwum.md) i [kursów](../rozpoznanie-kursow.md).

**Przepływ danych:**

`archiwum + pomocniczy GTFS → przygotowanie danych → SQLite → generator raportu → statyczny katalog HTML`

- Kod powstaje w `/workspace/src/`: projekt uv z `pyproject.toml`, plikiem blokady, pakietem `ztm_viz`, zasobami przeglądarkowymi i testami. Dane pochodne i raporty trafiają do `/workspace/outputs/ztm/`.
- Źródłem raportowanego opóźnienia jest archiwalny GPS. GTFS dostarcza pomocniczych tras, przystanków i nazw; jego kalendarz nie ogranicza analizowanego okresu.
- SQLite przechowuje obserwacje, pochodzenie, przypisania do kursów, odcinki i wyniki kontroli jakości. Jest odtwarzalnym wynikiem przetwarzania.
- Raport jest katalogiem plików statycznych z lokalnymi zasobami JavaScript i CSS, udostępnianym przez dowolny serwer plików statycznych ([ADR 0004](../adr/0004-statyczny-raport-przez-http.md)). Dane szczegółowe kursu pobiera dopiero po jego wybraniu. Nie potrzebuje serwera aplikacyjnego.

**Technologie:** pełny Python 3.15 zarządzany przez [uv](https://docs.astral.sh/uv/concepts/python-versions/), SQLite, Shapely 2, pyproj 3, pytest; w przeglądarce [Leaflet 1.9.4](https://leafletjs.com/reference-1.9.4.html), Canvas dla mapy, SVG dla wykresu i Web Worker dla agregacji. Zależności Pythona zostają utrwalone w pliku blokady.

Systemowemu Pythonowi 3.15.2 brakuje modułu `_decimal`, dlatego projekt korzysta z interpretera 3.15 zarządzanego przez uv i przypiętego w `.python-version`. Shapely 2.2 i pyproj 3.8 mają gotowe pakiety dla tej wersji.

## 2. Interfejs uruchamiania i wyniki

Udostępnić trzy polecenia uruchamiane z katalogu projektu. Poniższy przykład wybiera linie 127 i 162; użytkownik podaje własną listę przez wymagany parametr `--lines`:

```bash
cd /workspace/src

uv run ztm-viz prepare \
  --archive /workspace \
  --gtfs /workspace/gtfsgoogle.zip \
  --lines 127 162 \
  --out /workspace/outputs/ztm/dataset.sqlite

uv run ztm-viz report \
  --dataset /workspace/outputs/ztm/dataset.sqlite \
  --out /workspace/outputs/ztm/report

uv run ztm-viz serve \
  --report /workspace/outputs/ztm/report \
  --port 8000
```

- `prepare --lines LINIA [LINIA ...]` przyjmuje jedną lub więcej publicznych nazw linii zgodnych z `routeShortName`. Oznaczenia są tekstem, więc mogą zawierać litery. Parametr jest wymagany; nie ma zaszytego zestawu domyślnego ani ograniczenia do 127 i 162.
- `prepare` przetwarza wszystkie pełne lokalne doby `Europe/Warsaw` dla wskazanych linii, zapisuje bazę oraz podsumowanie jakości. Doba jest pełna, gdy próby pobrania obejmują ją od początku do końca. Luki wewnątrz doby trafiają do podsumowania, ale jej nie wykluczają. Niepełne doby na krańcach archiwum są pomijane i wymieniane w podsumowaniu; dla obecnego archiwum zakres to 4–10 listopada 2026 r. Opcjonalne `--from DATA --to DATA` zawężają zakres do wskazanych pełnych dób.
- `prepare` zachowuje identyfikację wejść, wybraną listę linii, zakres dób, wersję reguł i parametry przygotowania.
- `report` generuje katalog z HTML, zasobami, geometrią, wkładami poszczególnych kursów do agregacji oraz szczegółami kursów. Listę linii, kierunków, wariantów i etykiety interfejsu wyprowadza z przygotowanego zbioru; nie utrzymuje osobnej stałej listy linii.
- Katalog raportu jest samodzielny i nadaje się do hostingu statycznego. Używa wyłącznie ścieżek względnych i standardowych rozszerzeń plików. Worker ładuje z osobnego pliku tego samego pochodzenia. Nie wymaga konfiguracji serwera ani wstępnie skompresowanych odpowiedzi. Stan wyboru odbiorcy zapisuje we fragmencie adresu (`#…`), więc działa także pod podkatalogiem. Otwarty przez `file://` wyświetla po polsku informację, że wymaga udostępnienia przez HTTP.
- `serve` uruchamia lokalny podgląd tego samego katalogu pod `127.0.0.1:8000` i nie dodaje do niego żadnych funkcji. Umieszczenie katalogu na hostingu pozostaje poza zakresem.
- Ponowne generowanie wyglądu raportu korzysta z SQLite i nie wymaga ponownego odczytania surowego archiwum.
- Wyniki są zapisywane atomowo. Baza powstaje w pliku tymczasowym zamienianym przez `os.replace`. Raport powstaje w katalogu tymczasowym obok docelowego i zastępuje go dopiero po pełnym zapisie. Przerwane przetwarzanie nie zastępuje wcześniejszego poprawnego wyniku.
- Błędy pojedynczych zapisów trafiają do podsumowania jakości; brak użytecznych danych lub niepoprawne wejście kończą polecenie błędem.

Podkład OpenStreetMap pobiera wyłącznie kafelki aktualnego widoku, zachowuje atrybucję i domyślne buforowanie przeglądarki. Raport jest otwierany przez HTTP zgodnie z [zasadami usługi kafelków](https://operations.osmfoundation.org/policies/tiles/). Niedostępność podkładu nie blokuje tras, przystanków ani wykresu.

## 3. Reguły przygotowania i obliczeń

### Obserwacje i kursy

- Odczytywać wszystkie próby pobrania GPS i dopasowywać manifesty po pełnym kluczu zapisu. Poprawny GPS z manifestu `partial` pozostaje użyteczny.
- Oddzielać czas pobrania od `generated`. Datę i porę obserwacji wyznaczać w `Europe/Warsaw`.
- Identyczne powtórzenia rekordu deduplikować, zachowując powiązania ze wszystkimi zapisami źródłowymi.
- Wersje tej samej obserwacji (pojazd i `generated`) różniące się tylko tym, że jedna ma przypisanie do kursu, a druga nie ma żadnego, nie są konfliktem. Obserwacja należy do kursu z wersji z przypisaniem i zachowuje powiązania z zapisami obu wersji. W tygodniu 4–10 XI jest to 7176 z 7408 różnic, a dla linii 127 i 162 wszystkie 26.
- Wersje z różnymi przypisaniami lub różnymi pomiarami (pozycja, opóźnienie, prędkość) oznaczać jako konflikt. Nie wybierać arbitralnie jednej wersji: obserwacja jest wyłączona ze wszystkich kursów, przerywa ciągłość dotkniętych fragmentów i trafia do podsumowania jakości.
- Roboczym kluczem kursu jest linia, zadanie przewozowe i archiwalny czas rozpoczęcia. Pojazd i wariant są przypisaniami fragmentów kursu.
- Zmiana pojazdu lub wariantu przerywa ciągłość potrzebną do obliczania zmiany opóźnienia. Równoległe sprzeczne przypisania wyłączają niejednoznaczny fragment, bez tworzenia dodatkowego głosu w medianie.
- Brak manifestu oznacza lukę pochodzenia, odrębną od poprawności samego rekordu GPS. Obserwacje z takiego zapisu są używane, mają oznaczoną lukę pochodzenia i są liczone w podsumowaniu jakości; obecne archiwum nie zawiera takich zapisów.
- Braki identyfikacji kursu wyłączają rekord z agregacji po kursach, zgodnie ze specyfikacją. Raportowana liczba pominiętych rekordów to liczba zdeduplikowanych obserwacji bez identyfikacji kursu, podawana dla każdej linii; liczba surowych rekordów trafia do podsumowania jakości.
- Obserwacje spoza przetwarzanych dób nie są wczytywane. Kurs przecinający granicę zakresu jest w widoku kursu oznaczony jako obcięty granicą zakresu.

### Warianty i kierunki

- Wariant pomocniczy łączyć po parze `routeId` i `tripId` z GPS oraz `route_id` i środkowej części `trip_id` z GTFS. Sam numer wariantu powtarza się w wielu liniach. `routeShortName` służy wyłącznie do wyboru linii przez `--lines`; obserwacje z `routeId` nieobecnym w GTFS, np. 10171 dla linii 171, należą do linii, ale ich warianty są raportowane jako nieobecne w rozkładzie pomocniczym.
- Kierunkiem jest `direction_id` dopasowanego wariantu. Etykietą kierunku jest cel (`trip_headsign`) jego najczęściej obserwowanego wariantu; pozostałe cele są wymienione obok.
- Warianty nieobecne w GTFS nie dają wartości odcinków ani wkładów do agregacji. Podsumowanie jakości podaje ich kursy i obserwacje dla każdej linii i wariantu. Nie wyprowadzać geometrii z obserwacji.
- Wariant, który w GTFS ma więcej niż jedną różną sekwencję słupków lub geometrię, oznaczać jako niejednoznaczny, wyłączać i raportować. Obecny ZIP nie zawiera takich wariantów; różne `shape_id` jednego wariantu mają w nim identyczną geometrię.

### Dopasowanie przestrzenne

- Współrzędne GPS i GTFS interpretować jako długość i szerokość geograficzną. Opis GPS wymienia EPSG:3857, ale wartości są stopniami ([rozpoznanie](../rozpoznanie-archiwum.md)). Obliczenia odległości wykonywać po projekcji do metrów, przez pyproj z `always_xy=True`.
- Dopasowywać obserwacje do uporządkowanej geometrii wariantu. Nie używać samego najbliższego przystanku.
- Przyjąć jawne początkowe parametry:
  - odległość od geometrii do **75 m**;
  - tolerancja cofnięcia **30 m**;
  - przerwa ciągłości powyżej **90 s**;
  - maksymalny przyrost drogi odpowiadający **100 km/h + 30 m marginesu**;
  - granica przystanku **25 m** przed rzutem słupka na geometrię;
  - przerwa między obserwacjami wyznaczającymi przejazd przez przystanek do **60 s**.
- Uwzględniać konkurujące rzutowania i kolejność całego fragmentu. Jeśli pozostają możliwe różne odcinki, oznaczać dopasowanie jako nieznane.
- Łączyć odcinki wariantów tylko przy zgodnych kierunkowych słupkach i zgodnym uporządkowanym przebiegu. Sam `shape_id` ani para nazw przystanków nie wystarczają.

### Granice odcinków i krańce

Zgodnie z [ADR 0005](../adr/0005-wartosc-przy-koncu-odcinka.md):

- Wartością przy końcu odcinka jest ostatnia rzeczywista obserwacja przed granicą przystanku kończącego odcinek. Musi leżeć za przystankiem początkowym, a następna obserwacja tego samego fragmentu kursu musi przekroczyć granicę w ciągu 60 s. Nie interpolować wartości opóźnienia. Przy wartości zapisywać jej odległość i czas do przystanku.
- Granica przystanku leży przed słupkiem, aby obserwacje postoju rozrzucone przez błąd GPS nie zmieniały wyniku. Postój na przystanku należy do następnego odcinka.
- Początkiem odcinka jest wartość przy końcu poprzedniego odcinka tego samego kursu. Odcinek przejechany w całości między dwiema obserwacjami nie ma wartości ani zmiany.
- Wartością na początku kursu jest pierwsza obserwacja z oznakami ruchu do 150 m od pierwszego słupka, przed granicą drugiego przystanku. Wcześniejsze obserwacje postoju z przypisaniem do kursu są prezentowane oddzielnie jako obserwacje przed odjazdem. Bez takiej obserwacji początek jest nieznany, a pierwszy odcinek może mieć poziom, ale nie zmianę. Jeżeli wartość początkowa i wartość przy końcu pierwszego odcinka pochodzą z tej samej obserwacji, zmiana jest nieznana.
- Przy krańcu wartością dojazdu jest ostatnia obserwacja z oznakami ruchu przed pierwszą obserwacją postoju w okolicy krańca (do 150 m od słupka), jeśli dzieli je najwyżej 60 s. Oznaką ruchu jest raportowana prędkość lub przesunięcie pozycji. Zastana pozycja postojowa, brak takiego przejścia lub niejednoznaczność dają nieznany wynik dojazdu.
- Wartość `delay` nie uczestniczy w rozpoznawaniu fazy. Ruchome zero pozostaje prawidłową raportowaną wartością; późniejsze obserwacje przy krańcu są prezentowane oddzielnie.

Parametry są początkowymi założeniami implementacyjnymi, zatwierdzanymi na podstawie diagnostyki etapu 2. Nie wolno wydłużać dopuszczalnych przerw ani uzupełniać braków tylko po to, aby uzyskać pełne pokrycie.

### Agregacja

- Każdy kurs wnosi najwyżej jedną wartość do danego odcinka.
- Kolor wynika z mediany opóźnienia przy końcu odcinka; szczegóły pokazują maksimum i liczbę kursów. Przy parzystej liczbie kursów mediana jest średnią dwóch środkowych wartości, klasyfikowaną przed zaokrągleniem: 300 s i 301 s dają 300,5 s, czyli kolor czerwony.
- Zmianę obliczać jako `koniec − początek` wewnątrz kursu, następnie wyznaczać jej medianę.
- Filtr poziomu wymaga końcowej obserwacji w wybranym czasie. Filtr zmiany wymaga obu końców w zakresie; liczebności mogą być różne.
- Godziny stosować do lokalnego czasu obserwacji, w przedziałach domkniętych z lewej strony. Zakres przez północ należy do nocy rozpoczętej w zaznaczonym dniu: piątek 22:00–02:00 obejmuje obserwacje od piątku 22:00 do soboty 02:00. Jeżeli taki zakres wychodzi poza ostatnią przetworzoną dobę, interfejs to zaznacza.
- Zachować uzgodnione kolory: **≤0 zielony, >0–300 s pomarańczowy, >300 s czerwony, brak wartości szary**.

## 4. Etapy realizacji

Każdy etap kończy się działającym, sprawdzalnym rezultatem. Testy zachowania powstają przed implementacją danej funkcji.

| Etap | Zakres | Warunek zakończenia |
|---|---|---|
| **1. Środowisko i import** | Projekt Python w `src/`, CLI `prepare` z wymaganym parametrem `--lines`, wybór pełnych dób, strumieniowy odczyt GPS, manifesty, deduplikacja, SQLite i diagnostyka. | Małe archiwum obejmujące powtórzenia, różne próby, brak manifestu, uszkodzony zapis i niepełne doby na krańcach daje oczekiwane obserwacje, zakres dób i liczniki. Wybór pojedynczej oraz kilku linii, także spoza zestawu 127/162, działa bez zmian kodu. Ponowne uruchomienie po błędzie działa poprawnie. |
| **2. Kursy i odcinki** | Rozpoznawanie przypisań, pomocnicze warianty GTFS, dopasowanie kolejnościowe, granice odcinków i faza przy krańcu. | Testy syntetyczne oraz [zestaw weryfikacyjny](../rozpoznanie-kursow.md#zestaw-kursów-do-weryfikacji) potwierdzają poprawne wartości i jawne odmowy dopasowania. Zmiana samych opóźnień nie zmienia rozpoznania fazy przejazdu. Diagnostyka na pełnym zakresie podaje dla każdego odcinka odsetek przejazdów z wartością i ze zmianą oraz rozkład odległości wartości od przystanku. Porównuje też prędkość przejazdów z wartością i bez niej. Parametry są zatwierdzane na tej podstawie. |
| **3. Eksport i statystyki** | CLI `report`, wersjonowany format danych, paczki wkładów według linii i dnia, szczegóły kursów na żądanie, agregacja w Workerze. | Znane przykłady dają dokładne mediany, maksima, zmiany i liczebności; filtry nie korzystają z median wcześniej zagregowanych grup. |
| **4. Raport interaktywny** | Mapa, wykres, filtry, lista kursów, widok pełnego kursu z oddzielnymi obserwacjami przed odjazdem i przy krańcu, powrót z zachowaniem wyboru, jakość i pochodzenie danych. | Test przeglądarkowy przechodzi od całego okresu do odcinka i kursu oraz z powrotem. Lista linii odpowiada przygotowanym danym, również dla konfiguracji bez 127 i 162. Działa także na małym ekranie i bez dostępnego podkładu ulic. Testy przechodzą na katalogu udostępnionym przez ogólny serwer plików statycznych pod podkatalogiem adresu, nie tylko przez `serve`; otwarcie przez `file://` pokazuje informację o wymaganym HTTP. |
| **5. Pełne archiwum i odbiór** | Przetworzenie wszystkich pełnych dób (dla obecnego archiwum 4–10 listopada) dla skonfigurowanych linii; pierwsza weryfikacja na zestawie 127/162, próbne uruchomienie dla tramwaju 8 i nocnej linii N8, raport jakości, pomiary wydajności, instrukcja uruchamiania po polsku. | Spełnione kryteria zatwierdzonej specyfikacji; każda prezentowana wartość ma ścieżkę do obserwacji źródłowej, a ograniczenia pokrycia są widoczne. Dla linii 8 i N8 raport powstaje bez zmian kodu, odcinki są wiarygodne w przeglądzie, a odmowy dopasowania są policzone i widoczne; nie jest to pełna weryfikacja tych linii. |

Wykres zachowuje osobne przebiegi rozbieżnych wariantów. Nie tworzy pozornej ciągłej trasy przez połączenie różnych odgałęzień. Kolory zawsze uzupełniają wartości i opisy tekstowe.

## 5. Weryfikacja i granice dowodów

**Testy automatyczne:**

- Konfiguracja linii: wymagany parametr `--lines`, wybór jednej i wielu linii, oznaczenie alfanumeryczne oraz linia spoza 127/162. Ten sam proces przygotowania i generowania raportu działa bez zmian kodu, a interfejs pokazuje wyłącznie linie z przygotowanego zbioru.
- Import: powtórzenia, ta sama obserwacja z przypisaniem i bez niego, sprzeczne przypisania lub pomiary tego samego czasu, brakujące pliki i manifesty, manifest `partial`, uszkodzony gzip, puste pola i poprawne zero.
- Kursy: chwilowy brak przypisania, zmiana wariantu lub pojazdu, równoległy konflikt, zachowanie wiarygodnych fragmentów.
- Warianty: ten sam numer wariantu w różnych liniach, `routeId` nieobecny w GTFS, wariant nieobecny w GTFS, wariant z kilkoma przebiegami, kierunek z kilkoma celami.
- Geometria: bliskie i powtarzające się przystanki, krótkie odcinki 58–101 m w Oliwie, cofnięcia, skrzyżowania, zbyt długie przerwy oraz niezgodny wariant.
- Wartość przy końcu odcinka: odcinek przejechany w całości między dwiema obserwacjami nie ma wartości ani zerowej zmiany; postój rozrzucony wokół słupka nie zmienia wyniku; przerwa ponad 60 s przy przystanku daje brak wartości.
- Krańce: ruchome zero, pierwsza obserwacja już podczas postoju, długi postój pod starym przypisaniem i brak obserwacji dojazdu.
- Początek kursu: postój przed odjazdem, pierwsza obserwacja już w ruchu, pierwsza obserwacja dalej niż 150 m od słupka, wartość początkowa i końcowa pierwszego odcinka z tej samej obserwacji.
- Statystyki: `2→5 min` daje wzrost `3 min`; `8→5 min` daje zmianę `−3 min`; powielenie zapisów nie zmienia wyniku; brak początku usuwa zmianę, ale może pozostawić poziom.
- Czas: lokalna data, zakres przez północ należący do nocy zaznaczonego dnia, pominięcie niepełnych dób, kurs obcięty granicą zakresu, kurs rozpoczęty przed filtrem i pełny kurs po wejściu w szczegóły.
- Przeglądarka: zgodność mapy i wykresu, zachowanie filtrów, widoczne braki, błąd pobrania kursu i udane ponowienie, bezpieczne wyświetlanie tekstów ze źródła, działanie spod podkatalogu ogólnego serwera statycznego.

Kontrole uruchamiać przez `uv run pytest` oraz `node --test`; scenariusze HTTP sprawdzać w Playwright. Testy przeglądarkowe nie pobierają masowo kafelków zewnętrznej mapy.

**Dane rzeczywiste:** wykorzystać dziewięć kursów z 9 i 10 listopada wymienionych w [zestawie weryfikacyjnym](../rozpoznanie-kursow.md#zestaw-kursów-do-weryfikacji), obejmujących oba kierunki obu linii, oraz sprawdzić dodatkowe kursy z pozostałych dni przed odbiorem. 722 zapisy GPS z tych dwóch okien potwierdzają konkretne przypadki brzegowe; nie dowodzą poprawności gotowego algorytmu ani kompletności tygodnia.

**Wydajność:** zmierzyć wielkość eksportu, pierwszy widok, filtrowanie i otwarcie kursu. Domyślne cele techniczne dla lokalnego HTTP: pierwszy widok do 5 sekund, ponowne filtrowanie już pobranych danych do 1 sekundy. Pomiar wyklucza czas pobierania zewnętrznych kafelków i podaje użyte środowisko.

Plan nie obejmuje publikacji na hostingu, zbierania nowych danych ani oceny trafności prognoz odjazdów. Surowe archiwum pozostaje niezmienione.
