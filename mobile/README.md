# Luna na telefonie

Wersja testowa Luny na Androida i iPhone'a (Flutter), w wyglądzie Luny z komputera.

- Ekran główny: gwiazdy, zegar, wyszukiwarka, kafelki, widgety (pogoda z Open-Meteo, seria dni, zadania).
- Strony w zaokrąglonych ramkach, pasek na dole: tarcza z licznikiem, adres, karty, menu. Wstecz i dalej w nagłówku strony.
- Gesty: pasek w bok – sąsiednia karta, pasek w górę – wszystkie karty, strona w dół – odświeżenie.
- Karty i przestrzenie: Otwarte · Na później · Prywatne, wyszukiwanie kart, menu karty po przytrzymaniu.
- Menu Luny w arkuszu od dołu, asystent AI (ChatGPT, Claude, Gemini, DeepSeek) i komunikatory.
- Dwie strony na ekranie: pionowo jedna pod drugą, poziomo obok siebie.
- Poziomo: jeden pasek u góry jak na komputerze, ekran główny w dwóch kolumnach.
- Podpowiedzi wyszukiwania z historii i z wybranej wyszukiwarki (wyłączysz w Ustawieniach).
- Blokada reklam i śledzenia (listy pobierane przy pierwszym uruchomieniu), YouTube bez reklam, tryb czytania, ciemny tryb stron.

## Budowanie

```bash
flutter pub get
flutter build apk --release
```

iOS: `flutter build ios --release` na Macu; do instalacji na iPhonie potrzebny jest podpis (konto Apple Developer).
GitHub buduje obie wersje automatycznie (`.github/workflows/mobile.yml`).
