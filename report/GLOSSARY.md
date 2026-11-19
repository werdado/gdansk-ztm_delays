# Wizualizacja archiwum ZTM

Pojęcia używane do interpretacji archiwalnych danych o komunikacji miejskiej. Rozróżnienia wynikają z lokalnej [dokumentacji GPS](docs/gps.md), [odjazdów](docs/departures.md) i [rozkładu](docs/gtfsgoogle.md).

## Pojęcia

**Linia**:
Usługa komunikacyjna oznaczona numerem znanym pasażerom, np. 127 lub 162. Może obejmować różne kierunki i warianty trasy.
_Unikaj_: Kurs, gdy mowa o całej linii

**Wariant trasy**:
Określony przebieg przejazdu i kolejność obsługiwanych przystanków w danym kierunku.
_Unikaj_: Kurs, gdy mowa o powtarzalnym przebiegu trasy

**Kierunek linii**:
Grupa wariantów trasy linii, które rozkład przypisuje do tej samej strony przejazdu („tam” lub „powrót”). Nie jest geograficznym kierunkiem jazdy pojazdu.
_Unikaj_: Kierunek jazdy, cel kursu

**Kurs**:
Pojedynczy przejazd linii według określonego wariantu trasy, odróżniany od innych przejazdów m.in. dniem i godziną rozpoczęcia.
_Unikaj_: Linia, wariant trasy

**Obraz zbiorczy opóźnień**:
Podsumowanie opóźnień wielu kursów w wybranym przedziale czasu. Jest powiązane z poszczególnymi kursami, których dane stanowią jego podstawę.
_Unikaj_: Przebieg pojedynczego kursu

**Odcinek między przystankami**:
Skierowany fragment przejazdu pomiędzy dwoma kolejnymi przystankami obsługiwanymi w danym wariancie trasy. Przejazd w przeciwnym kierunku jest innym odcinkiem.
_Unikaj_: Cała trasa, gdy mowa o jej fragmencie

**Typowe opóźnienie**:
Mediana wartości opóźnienia poszczególnych kursów w rozpatrywanym miejscu i przedziale czasu, z równą wagą każdego kursu. Nie opisuje największego zaobserwowanego opóźnienia.
_Unikaj_: Średnia, maksymalne opóźnienie

**Opóźnienie przy końcu odcinka**:
Raportowane opóźnienie kursu z ostatniej obserwacji przed przystankiem kończącym odcinek między przystankami. Jest wartością reprezentującą kurs na tym odcinku, ale nie stanowi pomiaru dokładnego czasu przyjazdu na przystanek.
_Unikaj_: Zmierzone opóźnienie przyjazdu, opóźnienie najbliższej obserwacji

**Zmiana opóźnienia na odcinku**:
Różnica między opóźnieniem przy końcu odcinka a opóźnieniem przy końcu poprzedniego odcinka tego samego kursu, obejmująca postój na przystanku początkowym. Wartość dodatnia oznacza wzrost opóźnienia, ujemna — jego zmniejszenie.
_Unikaj_: Poziom opóźnienia, różnica typowych opóźnień różnych grup kursów

**Obserwacje przed odjazdem**:
Obserwacje postoju pojazdu przy pierwszym przystanku, zarejestrowane już z przypisaniem do kursu, ale przed rozpoczęciem przejazdu. Ich opóźnienie nie jest wartością początku kursu.
_Unikaj_: Opóźnienie odjazdu

**Obserwacje przy krańcu po dojeździe**:
Obserwacje pojazdu z okresu po rozpoznanym dojeździe w okolice końca trasy, również wtedy, gdy źródło nadal przypisuje go do zakończonego przejazdu. Ich opóźnienie nie zastępuje wartości z dojazdu.
_Unikaj_: Opóźnienie na dojeździe

**Zapis źródłowy**:
Odpowiedź źródła danych zachowana podczas jednej próby pobrania. Kolejne zapisy mogą zawierać te same obserwacje.
_Unikaj_: Obserwacja, gdy mowa o całej odpowiedzi źródła

**Obserwacja pozycji**:
Pozycja pojazdu zarejestrowana przez źródło w określonym czasie. Czas jej rejestracji jest odrębny od czasu pobrania zapisu, który ją zawiera.
_Unikaj_: Aktualna pozycja, jeśli nie ustalono świeżości danych

**Raportowane opóźnienie**:
Odchylenie od rozkładu podane przez źródło; wartość ujemna oznacza jazdę przed czasem. Samo w sobie nie ustala faktycznego czasu przyjazdu ani odjazdu.
_Unikaj_: Zmierzone opóźnienie odjazdu

**Prognoza odjazdu**:
Przewidywany czas odjazdu pojazdu z konkretnego słupka przystankowego. Nie stanowi potwierdzenia, że odjazd nastąpił w tym czasie.
_Unikaj_: Faktyczny odjazd

**Odjazd rozkładowy**:
Planowany czas odjazdu; w danych o odjazdach może być podany zastępczo, gdy prognoza jest niedostępna.
_Unikaj_: Prognoza, potwierdzony punktualny odjazd

**Słupek przystankowy**:
Pojedyncze miejsce obsługi pasażerów identyfikowane odrębnie w danych o odjazdach. Różni się od zespołu pobliskich słupków noszących wspólną nazwę przystanku.
_Unikaj_: Zespół przystankowy
