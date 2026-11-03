# Handoff: ciągłe zbieranie danych ZTM

## Uzgodniony zakres

Kolektor działa **bez daty końcowej, do ręcznego wyłączenia przez użytkownika**. Obejmuje całą sieć i wszystkie rekordy publikowane przez poniższe źródła. Nie wybieramy konkretnych linii, kierunków ani godzin. Ustalenie o ręcznym wyłączeniu zastępuje pierwotny 10-dniowy limit PoC.

Wybrana implementacja: trzy Cloudflare Workers uruchamiane co minutę, z przesunięciami 0/20/40 sekund, zapisujące każde pełne pobranie jako gzip do wspólnego bucketa R2. Użytkownik zajmuje się wdrożeniem; bieżące prace obejmują implementację i lokalne testy.

| Co zbieramy | Bezpośredni adres | Częstotliwość |
|---|---|---|
| GTFS-RT All: aktualizacje kursów i pozycje pojazdów, protobuf | https://ckan2.multimediagdansk.pl/gtfs-rt | Co 20 sekund |
| Pozycje GPS, opóźnienia raportowane przez ZTM i jakość GPS, JSON v2 | https://ckan2.multimediagdansk.pl/gpsPositions?v=2 | Co 20 sekund |
| Prognozy odjazdów ze wszystkich przystanków wraz z wpisami rozkładowymi, JSON | https://ckan2.multimediagdansk.pl/departures | Co 20 sekund |

GTFS-RT All zawiera oba rodzaje informacji; nie ustalono dodatkowego pobierania osobnych feedów TripUpdates i VehiclePositions.

## Co zachowujemy

- Oryginalne pliki źródłowe, bez filtrowania i przepisywania zawartości; bezstratna kompresja jest dopuszczalna.
- Informację o źródle i czasie pobrania; źródłowe znaczniki czasu pozostają w danych.
- Bez automatycznego usuwania i bez automatycznego zatrzymania kolektora. Użytkownik decyduje o terminie wyłączenia i dalszej retencji. Nie ustalono obecnie docelowej wieloletniej architektury.

## Istotne rozróżnienia

Pozycje GPS są obserwacjami. Opóźnienie raportowane przez system i prognozy przystankowe nie stanowią gwarancji rzeczywistego czasu odjazdu. Zachowujemy wszystkie rekordy, aby później móc je rozróżnić. Brak danych nie oznacza zerowego opóźnienia.

GTFS-RT wnosi gotowe powiązanie z pełnym identyfikatorem kursu GTFS i kolejnością przystanków. JSON-y zawierają dodatkowe pola źródłowe. Dlatego zachowujemy oba formaty. Jednorazowy statyczny GTFS może nie odzwierciedlać późniejszych zmian rozkładu; użytkownik świadomie ograniczył ten element PoC.

## Źródła i stan prac

- Katalog danych: https://ckan.multimediagdansk.pl/dataset/tristar
- GTSF <https://ckan.multimediagdansk.pl/dataset/tristar/resource/30e783e4-2bec-4a7d-bb22-ee3e3b26ca96> (Statyczny rozkład GTFS, ZIP)
