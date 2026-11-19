# Opis danych GPS 

Zasób zawiera wywołanie zwracające informację o pozycjach GPS wszystkich pojazdów realizujących kursy linii ZTM w Gdańsku w czasie określonym przez wartość DataGenerated. Ze względów bezpieczeństwa zbiór zwraca informacje pochodzące z pamięci cache. Opóźnienie, związane z aktualizacją danych, wynikające z jego wprowadzenia wynosi ok. 20 sekund niezależnie dla każdego pojazdów. Źródłem danych jest webserwis stworzony w tym celu w ramach systemu TRISTAR.

Ze zbioru wykluczono pojazdy Zarządu Komunikacji Miejskiej w Gdyni (za wyjątkiem tych realizujących linię wspólną) oraz pojazdy nieposiadające przypisania zadania przewozowego i pojazdy z wyłączonymi urządzeniami pokładowymi.

Dla pojazdów, które nie są rozpoznane jako realizujące zadanie przewozowe (są tylko włączone i przypisane do zadania przewozowego), usługa dostarczy jedynie: VehicleService, VehicleCode, VehicleID, Lat oraz Lon. Pozostałe dane związane z zadaniem przewozowym zostaną wypełnione pustym ciągiem znaków ("").

Jeżeli pojazdy stracą połączenie z serwerem TRISTAR, ich pozycja GPS przestanie być aktualizowana. Nieaktualizowane pozycje GPS są trzymane w pamięci cache webservice’u przez maksymalnie 5 minut po otrzymaniu ostatnich danych. Po tym czasie są usuwane z pamięci cache.

W odpowiedzi na wywołanie otrzymuje się zasób zawierający następujące dane:

- lastUpdate – data aktualizacji danych z systemów źródłowych; data w formacie ISO-8601 (UTC)
- vehicles – zawiera obiekty przechowujące informacje dla pojedynczego pojazdu, który jest poprawnie przypisany do zadania przewozowego ZTM w Gdańsku w systemie TRISTAR; pojedynczy obiekt zawiera następujące pola:
  - generated - stempel czasowy oznaczający czas, kiedy pozycja GPS pojazdu została zarejestrowana w systemie; format ISO-8601 (UTC)
  - routeShortName - kod publiczny linii, którą realizuje pojazd; wartość routeShortName z zasobu [**Lista linii**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851); ciąg znaków
  - routeId – identyfikator linii, do której przynależy wariant; wartość routeId z zasobu [**Lista linii**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851); liczba całkowita
  - tripId - kod publiczny wariantu/trasy, po której porusza się pojazd; wartość tripId z zasobu [**Lista tras**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/b15bb11c-7e06-4685-964e-3db7775f912f); liczba całkowita
  - vehicleCode – numer boczny pojazdu realizującego kurs; ciąg znaków
  - vehicleService - kod zadania przewozowego pojazdu; wartość busServiceName z zasobu [**Rozkład jazdy**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/a023ceb0-8085-45f6-8261-02e6fcba7971); ciąg znaków w formacie "xxx-yy", gdzie xxx – identyfikator linii, wartość routeId z zasobu [**Lista linii**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851) dopełniony z przodu zerami do trzech cyfr, yy - numer brygady dopełniony z przodu zerami do dwóch cyfr
  - vehicleId – wewnętrzny unikalny identyfikator pojazdów transportu zbiorowego w systemie TRISTAR; liczba całkowita
  - speed - szybkość pojazdu w momencie, kiedy opóźnienie zostało oszacowane; wartość podawana w km/h;
  - delay - podany w sekundach czas opóźnienia. Wartość ujemna oznacza przyspieszenie w stosunku do czasu rozkładowego; liczba całkowita
  - lat - szerokość geograficzna pozycji GPS pojazdu; format: DDD.DDDDD (system odniesienia EPSG:3857 znany też jako WGS84/Pseudo-Mercator)
  - lon - długość geograficzna pozycji GPS pojazdu; format: DDD.DDDDD (system odniesienia EPSG:3857 znany też jako WGS84/Pseudo-Mercator)
  - gpsQuality – jakość zarejestrowanego sygnału GPS. Możliwe wartości to:
    - 0: Brak sygnału GPS
    - 1: liczba widocznych satelitów niewystarczająca do pracy w trybie 2D
    - 2: praca odbiornika GPS w trybie 2D
    - 3: praca odbiornika GPS w trybie 3D
  - headsign – kierunek, w którym realizowany jest bieżący przejazd/kurs; najczęściej nazwa ostatniego przystanku dla pasażera.
  - direction – geograficzny kierunek jazdy z przedziału 0-315 z krokiem co wartość 45, gdzie 0 oznacza północ a 315 - północny zachód
  - scheduledTripStartTime – rozkładowy czas rozwpoczęcia kursu; format ISO-8601 (UTC)
