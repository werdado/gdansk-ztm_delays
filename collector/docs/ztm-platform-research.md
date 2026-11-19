# ZTM: platforma dla 10-dniowego PoC

Aktualizacja decyzji: użytkownik wybrał trzy Workery z przesunięciami 0/20/40 sekund, gzip wszystkich trzech źródeł i wspólny R2. Kolektor ma działać stale do ręcznego wyłączenia; bez limitu dziesięciu dni. Wdrożeniem zajmuje się użytkownik. Poniższe wyliczenia dziesięciodniowe pozostają historycznymi przykładami rozmiaru i kosztów; aktualna obsługa jest opisana w [README](./README.md).

Stan dokumentacji: **2026-11-03**. Zakres: [handoff](./ztm-poc-handoff.md). To ocena wykonalności i kosztów, bez wdrożenia.

**Rekomendacja: Cloudflare Workers Paid + R2 Standard to rozsądny wybór dla tego PoC. Workers Free jest wariantem do sprawdzenia pomiarem, nie potwierdzonym rozwiązaniem.** Najważniejsza różnica to budżet CPU; sam harmonogram minutowy z trzema pobraniami w odstępach 20 sekund mieści się w limicie czasu wykonania. Jeżeli istotne jest ścisłe utrzymanie odstępów także pomiędzy minutami, trzeba osobno zweryfikować opóźnienia harmonogramu. Poniżej rozdzielono udokumentowane limity, pomiary źródeł oraz wnioski projektowe.

## Wielkość zadania i pomiar źródeł

10 dni × 24 h × 180 rund/h = **43 200 rund**; trzy źródła dają **129 600 plików źródłowych**. Minutowy handler wykona się 14 400 razy, czyli 1 440 razy dziennie. Jeden dodatkowy manifest na rundę daje łącznie 172 800 zapisów; osobny plik metadanych dla każdego pobrania — 259 200. Retry i odczyty kontrolne zwiększą te liczby.

Pomiar wykonany przez głównego agenta 2026-11-03 o 13:47:38–39 UTC: zwykły GET przez `curl`, bez nagłówka `Accept-Encoding`, wszystkie odpowiedzi HTTP 200. Kompresja lokalna Python `gzip`, poziom 6, `mtime=0`.

| Źródło | Bajty odpowiedzi | Bajty gzip | Czas GET lokalnie |
|---|---:|---:|---:|
| GTFS-RT All | 176 398 | 52 218 | 0,53 s |
| GPS v2 | 114 785 | 17 387 | 0,61 s |
| Departures | 4 201 386 | 307 591 | 1,44 s |
| **Jedna runda** | **4 492 569** | **377 196** | — |
| **43 200 identycznie dużych rund** | **194,08 GB** | **16,29 GB** | — |

To **pojedyncza próbka, nie prognoza pojemności ani benchmark Workers**. Wielkość danych zmienia się w czasie. JSON-y miały `Content-Length`; protobuf go nie miał. W dodatkowej próbie około 13:49 UTC `Accept-Encoding: gzip` nie spowodował kompresji żadnego źródła: brak `Content-Encoding` i sygnatury gzip. Oszacowanie 16,29 GB wymaga więc kompresji po stronie kolektora lub późniejszego przetwarzania. Surowe dane pozostają pełnoprawnym wariantem PoC.

## Workers: twarde limity

| Właściwość | Free | Paid |
|---|---:|---:|
| CPU jednego wywołania HTTP | 10 ms | domyślnie 30 s, maks. 5 min |
| CPU jednego crona częściej niż co godzinę | **10 ms** | **30 s** |
| CPU crona co godzinę lub rzadziej | 10 ms | 15 min |
| Czas rzeczywisty pojedynczego crona, łącznie z oczekiwaniem | 15 min | 15 min |
| Pamięć izolatu | 128 MB | 128 MB |
| Wywołania Free | 100 000/dzień | bez dziennego limitu |
| Zewnętrzne subrequesty / wywołanie | 50 | domyślnie 10 000 |
| Subrequesty do usług wewnętrznych | 1 000 | domyślnie 10 000 |
| Połączenia oczekujące jednocześnie na nagłówki | 6 | 6 |

Oczekiwanie na sieć nie zużywa CPU. Free nie otrzymuje 30 sekund CPU przez użycie `scheduled()`. Limit obejmuje całe wywołanie, a nie każdy z dziewięciu plików. Przekroczenie może zakończyć wykonanie. [Limity Workers](https://developers.cloudflare.com/workers/platform/limits/)

Wniosek z liczby operacji: typowa minuta to 9 zewnętrznych GET i 9 zapisów R2, ewentualnie 3 manifesty. Quoty żądań i subrequestów pozostawiają duży zapas. Pobieranie trzech źródeł równolegle wymaga kontroli nakładania się kolejnych rund.

## Jak uzyskać odstępy 20 sekund

Cloudflare obsługuje pięciopolowy cron; najmniejsza jednostka to minuta (`* * * * *`). Dodanie, zmiana lub usunięcie crona może propagować się do 15 minut. [Cron Triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/)

Proponowany model: jedno wywołanie na minutę, rundy dla czasu zaplanowanego +0/+20/+40 s. `scheduledTime` zawiera nominalny czas wywołania. `scheduler.wait()` pozwala asynchronicznie czekać określoną liczbę milisekund. Cała praca powinna pozostać objęta oczekiwanym Promise handlera. [Scheduled Handler](https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/), [Scheduler API](https://developers.cloudflare.com/workers/runtime-apis/scheduler/)

**Wniosek, nie gwarancja platformy:** to wykonalny mechanizm przybliżonego próbkowania co 20 sekund. Nie znaleziono w przytoczonej dokumentacji gwarancji maksymalnego opóźnienia crona ani dostarczenia dokładnie raz. Oczekiwanie 20 s *po zakończeniu* poprzedniego pobrania dodawałoby czas transferu do interwału. Wyznaczanie terminów względem `scheduledTime` ogranicza dryf, ale spóźnionego pomiaru nie da się odzyskać. Należy zachować czas planowany, rzeczywisty czas pobrania, wynik każdej próby i luki; określić zachowanie przy spóźnieniu, powtórzeniu i nakładaniu się wywołań. Warunek końca 10 dni powinien działać również w samym kolektorze ze względu na propagację usuwania crona.

## R2: streaming i kompresja

R2 przyjmuje `ReadableStream`, bufory i inne typy; ma też metadane użytkownika. [Workers API R2](https://developers.cloudflare.com/r2/api/workers/workers-api-reference/) Limit pojedynczego uploadu to 5 GiB, całego obiektu 5 TiB, a metadanych 8 192 bajty. [Limity R2](https://developers.cloudflare.com/r2/platform/limits/)

**Ważny szczegół:** kod wykonawczy Cloudflare wymaga znanej długości streamu przy zapisie R2 i odrzuca stream bez niej. [Źródło workerd, `doR2HTTPPutRequest`](https://github.com/cloudflare/workerd/blob/main/src/workerd/api/r2-rpc.c%2B%2B#L213) `FixedLengthStream` wymaga wcześniejszej znajomości dokładnej liczby bajtów; nie wylicza jej za nas. [FixedLengthStream](https://developers.cloudflare.com/workers/runtime-apis/streams/transformstream/)

Dla obecnych rozmiarów prosty wariant to buforowanie pojedynczej odpowiedzi z limitem rozmiaru, następnie zapis. Nie należy zakładać, że każdy `response.body` albo wynik `CompressionStream` można bezpośrednio przekazać do R2: po kompresji końcowa długość nie jest z góry znana. Buforowanie skompresowanego wyniku rozwiązuje ten problem przy małych plikach; wymaga ograniczenia współbieżności i pamięci.

Workers udostępnia `CompressionStream` dla gzip/deflate. Dokumentacja nie daje zwolnienia kompresji z limitu CPU. [Web APIs](https://developers.cloudflare.com/workers/runtime-apis/web-standards/#compression-streams) **Nie potwierdzono**, że kompresja około 13,48 MB danych na minutowe wywołanie wraz z obsługą zapisów zmieści się w Free. Ocena wymaga pomiaru rzeczywistego CPU całego handlera na platformie. Lokalny pomiar gzip tego nie rozstrzyga.

## Koszty i retencja

Workers Paid kosztuje minimum **5 USD/miesiąc na konto**, obejmuje 10 mln wywołań i 30 mln ms CPU miesięcznie. Nasze 14 400 wywołań wykorzysta cały pakiet CPU dopiero przy średniej około 2,08 s CPU/wywołanie, zakładając brak innych obciążeń konta. Nie należy zakładać opłaty proporcjonalnej do 10 dni. [Cennik Workers](https://developers.cloudflare.com/workers/platform/pricing/)

R2 Standard obejmuje miesięcznie **10 GB-month, 1 mln operacji A i 10 mln operacji B**; egress jest bezpłatny. Ponad pakiet: 0,015 USD/GB-month, 4,50 USD/mln A, 0,36 USD/mln B. PUT to A. Zużycie zaokrągla się w górę do GB-month i miliona operacji. GB-month jest średnią dziennych maksimów przez okres 30 dni. Standard nie ma minimalnego okresu przechowywania; Infrequent Access nie obejmuje darmowego pakietu i ma minimum 30 dni. [Cennik R2](https://developers.cloudflare.com/r2/pricing/)

Wyliczenie z próbki, po zakończeniu zbierania, dla **pełnego kolejnego miesiąca zachowania całego archiwum**, przy niewykorzystanym pakiecie:

| Wariant | Rozmiar | Storage R2 / pełny miesiąc |
|---|---:|---:|
| Bez kompresji | 194,08 GB | `(195 − 10) × 0,015` = **2,775 USD** |
| gzip według lokalnej próbki | 16,29 GB | `(17 − 10) × 0,015` = **0,105 USD** |

Pierwszy miesiąc zależy od narastania archiwum i dat rozliczenia. Metadane, inne dane konta i rzeczywiste rozmiary zmienią koszt. Planowane zapisy mieszczą się w pakiecie A nawet z osobnymi metadanymi.

Zgodnie z handoffem nie ustawiamy automatycznego usuwania ukończonych plików. Domyślna reguła siedmiodniowa R2 dotyczy niedokończonych uploadów multipart, nie retencji gotowego archiwum. [Lifecycle R2](https://developers.cloudflare.com/r2/buckets/object-lifecycles/) Po 10 dniach zatrzymujemy pobieranie; przechowywanie i jego naliczanie trwają do późniejszej decyzji.

## Krótkie porównanie AWS

| Wariant | Ocena dla tego PoC |
|---|---|
| Workers Free + R2 | Możliwe bez kompresji po potwierdzeniu CPU i zachowania harmonogramu; zerowy koszt compute nie oznacza zerowego storage. |
| Workers Paid + R2 | Najprostszy wybór przy akceptacji około 5 USD za compute; usuwa główne ryzyko bardzo małego budżetu CPU, lecz nie gwarantuje idealnego harmonogramu. |
| Lambda + EventBridge + S3 | Wykonalne, może wykorzystać wolne limity konta; dodatkowe oczekiwanie wewnątrz Lambdy jest płatnym czasem działania. |
| EC2 + S3 | Stały proces łatwo realizuje własny zegar 20 s; wymaga nadzoru procesu, restartów, konfiguracji systemu i opłaty za 240 h instancji. |

EventBridge Scheduler ma **60-sekundową precyzję** wywołania, nawet bez flexible time window, oraz minutową jednostkę najkrótszego harmonogramu. Starsze scheduled rules również mają minimum minutę i możliwe kilkusekundowe opóźnienie. To nie jest natywne rozwiązanie do precyzyjnego wyzwalania co 20 s. [Scheduler](https://docs.aws.amazon.com/scheduler/latest/UserGuide/schedule-types.html), [Scheduled rules](https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-create-rule-schedule.html)

Zwykła Lambda ma maksymalnie 15 min wykonania. Dla `0/20/40 s` trzeba zwiększyć domyślny timeout 3 s. [Timeout Lambda](https://docs.aws.amazon.com/lambda/latest/dg/configuration-timeout.html) Naliczana jest pamięć × czas wykonania, więc zwykłe `sleep`/oczekiwanie też kosztuje. Pakiet miesięczny: 1 mln żądań i 400 000 GB-s. Dla 512 MB i 14 400 wywołań samo 40 s oczekiwania/czasu do ostatniej rundy to **288 000 GB-s**, plus końcowy transfer i pozostałe narzuty. Może zmieścić się w niewykorzystanym pakiecie, ale nie należy przyjmować zerowego rachunku bez pomiaru. [Cennik Lambda](https://aws.amazon.com/lambda/pricing/) Scheduler obejmuje 14 mln wywołań miesięcznie. [Cennik EventBridge](https://aws.amazon.com/eventbridge/pricing/#Scheduler)

Przykładowe stawki S3 Standard w US East: 0,023 USD/GB-month i 0,005 USD/1 000 PUT; same 129 600 plików to około **0,648 USD za PUT**, plus metadane, storage i ewentualne odczyty/transfer. Region i dostępne kredyty wymagają sprawdzenia na właściwym koncie. [Oficjalny przykład kosztów AWS](https://docs.aws.amazon.com/solutions/latest/live-streaming-on-aws-with-amazon-s3/cost-example-1.html), [Cennik S3](https://aws.amazon.com/s3/pricing/)

EC2 nalicza czas od uruchomienia do zatrzymania/terminacji; koszt PoC to 240 h × cena instancji plus dysk i storage. [EC2 On-Demand](https://aws.amazon.com/ec2/pricing/on-demand/) Pojedynczy publiczny IPv4 przy 0,005 USD/h dodaje **1,20 USD za 10 dni** przed kredytami. [Cennik VPC](https://aws.amazon.com/vpc/pricing/#Public_IPv4_Address)

## Co pozostaje do potwierdzenia

- Rzeczywiste CPU i pamięć handlera, szczególnie z kompresją, oraz zachowanie przy większych odpowiedziach.
- Opóźnienia crona i rzeczywiste odstępy pobrań; kryterium akceptacji brakujących lub spóźnionych rund.
- Stan pakietów rozliczeniowych konta i data okresu rozliczeniowego.
- Wielkość danych w różnych porach doby; pojedyncza próbka nie pozwala oszacować maksimum.

Nie wdrożono ani nie uruchomiono kolektora. Wskazane koszty są w USD, przed podatkami; nie stanowią prognozy gwarantowanej.

## Doprecyzowanie: trzy Workery i ZIP dwóch źródeł

Trzy wdrożenia tego samego kolektora mogą używać jednego bucketa R2. Każde ma cron `* * * * *`, a konfiguracja określa przesunięcie 0, 20 albo 40 sekund. Cloudflare nie obsługuje pola sekund w cron; drugie i trzecie wdrożenie muszą poczekać w handlerze do swojego terminu. To 4 320 wywołań dziennie łącznie. Free dopuszcza pięć Cron Triggers na konto, więc trzy mieszczą się, o ile pozostałe zadania nie zajmują limitu. Każde wywołanie ma osobne 10 ms CPU i pobiera wszystkie trzy źródła tylko raz. Rozdzielenie zmniejsza pracę na wywołanie, ale kompresja nadal wymaga pomiaru CPU. [Cron](https://developers.cloudflare.com/workers/configuration/cron-triggers/), [limity Workers](https://developers.cloudflare.com/workers/platform/limits/)

Klucze obiektów muszą zawierać źródło i termin pomiaru, z jawną polityką ponowień; wspólny bucket nie wymaga blokady dla zapisów do różnych kluczy. Przesunięcia nie gwarantują dokładnego czasu pobrania, jeśli sam cron uruchomi się z opóźnieniem.

**R2 nie ma limitu sumarycznych danych ani liczby obiektów w buckecie.** Darmowe 10 GB-month jest miesięcznym pakietem rozliczeniowym na konto, a nie twardym limitem pojemności. Dodatkowe dane są płatne. Limit uploadu jednoczęściowego to około 5 GiB, a całego obiektu około 5 TiB (dokumentacja precyzuje 4,995 TiB); próbki mają rozmiary wielokrotnie mniejsze. [Limity R2](https://developers.cloudflare.com/r2/platform/limits/), [cennik R2](https://developers.cloudflare.com/r2/pricing/)

Na tych samych zachowanych próbkach wykonano również rzeczywisty ZIP: Python `zipfile`, `ZIP_DEFLATED`, poziom 6, po jednym pliku w archiwum. Protobuf: **52 318 B ZIP**; departures: **307 701 B ZIP**; GPS pozostawiony jako JSON: **114 785 B**. Razem **474 804 B/rundę**, czyli **20,51 GB/10 dni** przy identycznych rozmiarach kolejnych próbek. To pomiar lokalny, nie benchmark kompresji w Workerze.

Przechowywanie takiego ukończonego archiwum przez cały następny miesiąc daje około `(21 − 10) × 0,015 = 0,165 USD` za storage R2, przy wolnym pakiecie i bez pozostałych danych/metadanych. Pierwszy miesiąc naliczany jest według rzeczywistego narastania danych. 129 600 zapisów nadal mieści się w milionie darmowych operacji A. Workers Paid, jeśli wybrany, jest osobną opłatą na konto — trzy wdrożenia nie oznaczają trzech opłat podstawowych po 5 USD. [Cennik R2](https://developers.cloudflare.com/r2/pricing/), [cennik Workers](https://developers.cloudflare.com/workers/platform/pricing/)
