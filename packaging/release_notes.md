## Co nowego w 1.0.13

- **Linux: Luna aktualizuje się sama** – AppImage i wersja z archiwum .tar.gz pobierają nowe wydanie w tle, sprawdzają sumę kontrolną i instalują je przy zamknięciu.
- **Android: aktualizacje z poziomu Luny** – Luna sama sprawdza nowe wydania, pobiera je i otwiera okno instalacji; w Ustawieniach jest też „Sprawdź aktualizacje”.
- **Android: stały podpis aplikacji** – od tej wersji kolejne wydania instalują się na poprzednich bez utraty danych. **Jeśli masz Lunę 1.0.12 lub starszą na telefonie, odinstaluj ją raz przed instalacją 1.0.13** (starsze wersje miały inny podpis).

W 1.0.12: samoaktualizacja i instrukcja instalacji w Lunie na macOS.

Wersja na iPhone'a jest gotowa w kodzie, ale do instalacji potrzebny jest podpis Apple (konto Apple Developer) – pojawi się później.

## Pobierz Lunę

| System | Plik | Jak zainstalować |
|---|---|---|
| **Windows 10 / 11** (zalecane) | `Luna-Windows.zip` | Rozpakuj (prawy przycisk → Wyodrębnij wszystkie) i uruchom `Luna.exe`. Luna zaproponuje instalację: skrót w menu Start i na pulpicie, odinstalowanie w ustawieniach Windows. |
| Windows – klasyczny instalator | `Luna-Windows-Setup.exe` | Uruchom i kliknij „Zainstaluj”. |
| **Linux** (x86_64) | `Luna-Linux-x86_64.AppImage` | Nadaj prawo uruchamiania (`chmod +x`) i uruchom dwuklikiem. |
| Linux (archiwum) | `Luna-Linux-x86_64.tar.gz` | Rozpakuj i uruchom `Luna/Luna`. |
| **macOS** (Apple M1 i nowsze) | `Luna-macOS-arm64.dmg` | Przeciągnij Lunę do Aplikacji. Za pierwszym razem: **Ustawienia systemowe → Prywatność i ochrona → Otwórz mimo to**. Bez ostrzeżenia – jedno polecenie w Terminalu (niżej). |
| **Android** 7 i nowsze (wersja testowa) | `Luna-Android.apk` | Pobierz na telefonie i otwórz. Android zapyta o zgodę na instalację aplikacji spoza Sklepu Play – zezwól przeglądarce, z której pobierasz. |

**Inteligentna kontrola aplikacji (Windows 11).** Jeśli jest włączona, Windows na razie zablokuje Lunę z wydania – nie pozwala uruchamiać nowych programów bez podpisu cyfrowego, a podpis Luny jest w przygotowaniu. Do tego czasu uruchom Lunę z kodu źródłowego (instrukcja w README).

**Ostrzeżenia przy pierwszym uruchomieniu.** Luna nie ma jeszcze podpisu cyfrowego, więc Windows może pokazać „System Windows ochronił ten komputer” (kliknij „Więcej informacji” → „Uruchom mimo to”), a macOS – „Rzecz »Luna« nie została otwarta”. Podpis jest w planach. Na macOS najprościej zainstalować Lunę poleceniem w Terminalu (pobiera najnowszą wersję do Aplikacji i uruchamia ją bez ostrzeżenia):

```bash
curl -fsSL https://raw.githubusercontent.com/z4k0lzakol/Luna/main/packaging/install-mac.sh | bash
```

Przy pierwszym uruchomieniu przewodnik przeniesie zakładki, historię i hasła z innej przeglądarki. Nowe wersje Luna pobiera i instaluje sama (Windows i macOS – na Macu ostrzeżenie trzeba więc ominąć tylko raz); na Linuksie proponuje pobranie.

**Code signing policy:** [zasady podpisywania kodu](https://z4k0lzakol.github.io/Luna/#podpis) – free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org) (zgłoszenie w przygotowaniu; to wydanie nie jest jeszcze podpisane).

Luna to projekt jednoosobowy; każde wydanie przechodzi automatyczne testy. Luna jest wolnym oprogramowaniem na licencji GNU GPL v3, bez gwarancji – [regulamin](https://z4k0lzakol.github.io/Luna/regulamin.html) · [prywatność](https://z4k0lzakol.github.io/Luna/privacy.html) · [strona Luny](https://z4k0lzakol.github.io/Luna/).

Linux i macOS to pierwsze wydania na tych systemach – jeśli coś nie działa, [zgłoś to](https://github.com/z4k0lzakol/Luna/issues/new/choose).
