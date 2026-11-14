# Jak pomóc w rozwoju Luny

Dziękujemy, że chcesz pomóc! Każde zgłoszenie błędu, pomysł i poprawka się liczy. Biorąc udział w projekcie, przestrzegasz [kodeksu postępowania](CODE_OF_CONDUCT.md).

## Zgłoś błąd

1. Sprawdź [listę zgłoszeń](https://github.com/z4k0lzakol/Luna/issues), czy ktoś już go nie opisał.
2. Kliknij **New issue → Zgłoś błąd** i wypełnij formularz: co robiłeś, co się stało, czego się spodziewałeś, wersja Luny (menu Pomoc → O Lunie) i system.
3. Jeśli Luna się zamknęła albo coś nie działa, dołącz ostatnie wpisy z pliku `C:\Users\<Ty>\.luna_bledy.log` – **najpierw usuń z nich dane prywatne** (adresy stron, nazwy kont).

**Luki bezpieczeństwa nie zgłaszaj publicznie** – zobacz [zasady bezpieczeństwa](SECURITY.md).

## Zaproponuj funkcję

Wybierz **New issue → Pomysł na funkcję**. Napisz, jaki problem ma rozwiązać i jak widzisz jej działanie. Luna ma być lekka, prywatna i prosta, więc przed dużą zmianą warto najpierw porozmawiać w zgłoszeniu.

## Przygotuj środowisko

Wymagania: Windows 10/11, Python 3.12+.

```bash
git clone https://github.com/z4k0lzakol/Luna.git
cd Luna
python -m pip install -r requirements.txt
python luna.py
```

## Zasady w kodzie

- **Interfejs po polsku**, prosty język, bez żargonu. Ikony rysowane wektorowo (funkcja `glyph`), bez emoji.
- **Ciemny, minimalistyczny wygląd** – używaj istniejących elementów: okna `LunaDialog`, listy `row_list`, przyciski z `footer(...)`.
- **Wydajność przed ozdobnikami**: bez odpytywania w tle, gdy nie jest potrzebne; nowe funkcje, które łączą się z siecią albo zużywają pamięć, powinny dać się wyłączyć (Ustawienia → Funkcje) i być opisane w [polityce prywatności](docs/privacy.html).
- **Prywatność**: żadnych kont, telemetrii ani serwerów Luny. Dane zostają na komputerze użytkownika.
- **Nie usuwaj istniejących funkcji** bez wcześniejszej rozmowy w zgłoszeniu.
- Plik `luna.py` ma końce linii **CRLF** – zachowaj je.
- Komentarze w kodzie piszemy po polsku, krótko: *dlaczego*, a nie *co*.

## Testy

Przed wysłaniem zmian uruchom testy:

```bash
python -I tests/test_site_features.py
```

`test_site_features.py` uruchamia prawdziwą Lunę na tymczasowym profilu (nie dotyka Twoich danych). Nowa funkcja powinna mieć swoje sprawdzenie w tym pliku.

Zmiany w blokadzie reklam (`adblock/`) sprawdź też testami z `tests/adblock` – każdy uruchamia się osobno, np.:

```bash
python -I tests/adblock/test_compiler.py
python -I tests/adblock/test_netfilter.py --no-bench
python -I tests/adblock/test_scriptlets.py
```

Testy z `_qt` w nazwie uruchamiają silnik przeglądarki i trwają ok. 20–30 s.

## Wyślij zmiany (pull request)

1. Zrób fork i osobną gałąź, np. `poprawka-zakladek`.
2. Opis commita pisz **po polsku i prostym językiem** – trafia do okna „Co nowego” w Lunie. Pierwsza linia: co się zmieniło dla użytkownika.
3. Jeśli zmiana dotyczy funkcji opisanych na stronie, zaktualizuj też `README.md` i pliki w `docs/` (strona, polityka prywatności, licencje).
4. Otwórz pull request i wypełnij szablon.

## Licencja wkładu

Luna jest na licencji [GNU GPL v3](LICENSE). Wysyłając zmiany, zgadzasz się, że Twój wkład będzie dostępny na tej samej licencji, i potwierdzasz, że masz do niego prawa (np. nie kopiujesz cudzego kodu na niezgodnej licencji).

---

**English:** Bug reports and ideas are welcome via [issues](https://github.com/z4k0lzakol/Luna/issues); security problems go to [SECURITY.md](SECURITY.md). The UI and commit messages are in Polish. Run `python -I tests/test_site_features.py` (and the scripts in `tests/adblock` for ad-blocker changes) before opening a pull request. Contributions are licensed under GPL v3.
