# Estymowane czasy odjazdów z przystanku - departures.json

Zasób zawiera dane dostępne w zasobie „Estymowane czasy odjazdów z przystanku” dla wszystkich słupków przystankowych. Klucz jest identyfikatorem słupka. Dane są pobierane dynamicznie, pochodzą z systemu TRISTAR. Dane są cache’owane dla każdego słupka niezależnie. Algorytm obliczający te dane bierze pod uwagę pozycję pojazdu względem wskazanego słupka przystankowego oraz dane o wykonaniu kursów, już zapisane w systemie. Dane mogą być nieprecyzyjne, z uwagi na dynamicznie zmieniające się warunki na drodze, interwał czasowy pomiędzy kolejnymi operacjami wyliczania próbek oraz wprowadzony czas cache’owania danych (20 sekund).

Rekord dla każdego słupka zawiera następujące dane:

- lastUpdate – data aktualizacji danych z systemów źródłowych; data w formacie ISO-8601 (UTC)
- departures – zawiera obiekty przechowujące informacje o estymowanych czasach przyjazdu na konkretny przystanek lub - w przypadku braku estymacji - powiązane dane rozkładowe. Obiekty są posortowane rosnąco względem pola estimatedTime. pojedynczy obiekt zawiera następujące pola:
  - w przypadku czasu estymowanego:
    - id – identyfikator, tworzony według zasady „T” + tripId + „R” + routeId; ciąg znaków
    - delayInSeconds – podany w sekundach czas opóźnienia. Wartość ujemna oznacza przyspieszenie w stosunku do czasu rozkładowego; liczba całkowita
    - estimatedTime – prognoza czasu odjazdu pojazdu z przystanku; w formacie ISO-8601 (UTC)
    - headsign – kierunek, w którym realizowany jest bieżący przejazd/kurs; najczęściej nazwa ostatniego przystanku dla pasażera; ciąg znaków
    - routeShortName - kod publiczny linii, którą realizuje pojazd; wartość routeShortName z zasobu [**Lista linii**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851); ciąg znaków
    - routeId – identyfikator linii, do której przynależy wariant; wartość routeId z zasobu [**Lista linii**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851); liczba całkowita
    - scheduledTripStartTime - rozkładowy czas rozpoczęcia kursu; format ISO-8601 (UTC)
    - tripId – identyfikator wariantu/trasy, do której przynależy słupek. Wartość tripId z zasobu „Lista tras”; liczba całkowita
    - status – wartość REALTIME; ciąg znaków
    - theoreticalTime – czas odjazdu wynikający z rozkładu jazdy; w formacie ISO-8601 (UTC)
    - timestamp – stempel czasowy określający czas obliczenia prognozy czasu odjazdu; format ISO-8601 (UTC)
    - trip – wewnętrzny identyfikator kursu; liczba całkowita
    - vehicleCode – numer boczny pojazdu realizującego kurs; liczba całkowita
    - vehicleId – wewnętrzny unikalny identyfikator pojazdów transportu zbiorowego w systemie TRISTAR; liczba całkowita
    - vehicleService - kod zadania przewozowego pojazdu; wartość busServiceName z zasobu [**Rozkład jazdy**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/a023ceb0-8085-45f6-8261-02e6fcba7971); ciąg znaków w formacie "xxx-yy", gdzie xxx – identyfikator linii, wartość routeId z zasobu [**Lista linii**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851) dopełniony z przodu zerami do trzech cyfr, yy - numer brygady dopełniony z przodu zerami do dwóch cyfr
  - w przypadku braku czasu estymowanego (dostępny jedynie czas rozkładowy):
    - id – identyfikator, tworzony według zasady „T” + tripId + „R” + routeId; ciąg znaków
    - delayInSeconds – wartość null
    - estimatedTime – czas odjazdu wynikający z rozkładu jazdy; w formacie ISO-8601 (UTC)
    - headsign – kierunek, w którym realizowany jest bieżący przejazd/kurs; najczęściej nazwa ostatniego przystanku dla pasażera; ciąg znaków
    - routeShortName - kod publiczny linii, którą realizuje pojazd; wartość routeShortName z zasobu [**Lista linii**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851); ciąg znaków
    - routeId – identyfikator linii, do której przynależy wariant; wartość routeId z zasobu „Lista linii”; liczba całkowita
    - scheduledTripStartTime - rozkładowy czas rozpoczęcia kursu; format ISO-8601 (UTC)
    - tripId – identyfikator wariantu/trasy, do której przynależy słupek. Wartość tripId z zasobu „Lista tras”; liczba całkowita
    - status – wartość SCHEDULED; ciąg znaków
    - theoreticalTime – czas odjazdu wynikający z rozkładu jazdy; w formacie ISO-8601 (UTC)
    - timestamp – stempel czasowy określający czas wygenerowania obiektu; format ISO-8601 (UTC)
    - trip – wewnętrzny identyfikator kursu; liczba całkowita
    - vehicleCode – wartość null
    - vehicleId – wartość null
    - vehicleService - kod zadania przewozowego pojazdu; wartość busServiceName z zasobu [**Rozkład jazdy**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/a023ceb0-8085-45f6-8261-02e6fcba7971); ciąg znaków w formacie "xxx-yy", gdzie xxx – identyfikator linii, wartość routeId z zasobu [**Lista linii**](http://ckan.multimediagdansk.pl/dataset/tristar/resource/22313c56-5acf-41c7-a5fd-dc5dc72b3851) dopełniony z przodu zerami do trzech cyfr, yy - numer brygady dopełniony z przodu zerami do dwóch cyfr
