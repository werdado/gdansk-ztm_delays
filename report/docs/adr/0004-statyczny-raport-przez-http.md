# Raport jako statyczny katalog udostępniany przez HTTP

Raport jest katalogiem plików statycznych — HTML, JavaScript, CSS i danych — który działa po udostępnieniu przez dowolny serwer plików statycznych, także pod podkatalogiem adresu; polecenie `ztm-viz serve` jest tylko lokalnym podglądem tego samego katalogu. Nie przewidujemy otwierania raportu przez `file://`, ponieważ agregacja w Web Workerze, pobieranie szczegółów kursu dopiero po jego wybraniu oraz nagłówek Referer wymagany przez usługę kafelków OpenStreetMap działają tylko przy dostępie przez HTTP. Odbiorca potrzebuje więc przeglądarki i adresu udostępnionego katalogu, a nie Pythona; samo umieszczenie katalogu na hostingu pozostaje poza zakresem pierwszej wersji.

## Rozważone możliwości

Pojedynczy plik HTML z osadzonymi danymi działałby bez serwera, ale wymagałby wczytania szczegółów wszystkich kursów naraz, a podkład mapy nie byłby dostępny.

Format plików danych w katalogu raportu (gzip rozpakowywany w przeglądarce) opisuje [ADR 0006](0006-dane-raportu-jako-gzip.md); nie zmienia on wymagania, że raport jest zwykłym katalogiem plików statycznych.
