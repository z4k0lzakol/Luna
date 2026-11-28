## Co nowego w 1.0.17

- **Telefon i tablet poziomo: strony znów widać** – przy kilku otwartych kartach strona bywała czarna, a ekran nowej karty był wąskim paskiem gwiazd. Teraz strony i ekran główny zawsze zajmują całą szerokość.
- **Dwie strony obok siebie bez przeskakiwania** – przy przewijaniu pasek zostaje na miejscu, więc strony nie zmieniają wysokości.
- **Pole adresu każdej z dwóch stron** – stuknij pole nad stroną, aby wpisać adres albo wyszukać tylko w niej.
- Linki otwierane z innych aplikacji działają bez błędów w tle.

## Co nowego w 1.0.16

- **Telefon i tablet: aktualizacje same po otwarciu** – zaraz po uruchomieniu Luna sprawdza nowe wydanie, pobiera je w tle (domyślnie tylko przez Wi-Fi) i proponuje instalację. Nowy ekran **Aktualizacje** (menu i Ustawienia): stan, postęp, opis zmian i przełączniki.
- **Podgląd strony w kartach** – zapisywany na dysku, więc widać go także po ponownym otwarciu Luny.
- **Usypianie nieużywanych kart** – po wybranym czasie (domyślnie 10 min) karta zwalnia pamięć, a przy braku pamięci Android usypia karty w tle od razu; uśpiona karta ma znaczek księżyca.
- **Tablet: więcej kart naraz** – lista kart dopasowuje liczbę kolumn do szerokości ekranu.
- **Komputer:** nowe wydanie jest sprawdzane kilka sekund po uruchomieniu.

## Co nowego w 1.0.15

- **Połączone urządzenia na Windows: kod QR działa** – w 1.0.14 Luna z wydania na Windows nie tworzyła certyfikatu, więc parowanie się nie zaczynało. Gdy połączenia nie da się włączyć, ustawienia pokazują teraz powód.
- **Telefon: bez zawieszania przy włączaniu połączenia** – certyfikat liczy się w tle, a błędy w tle nie zamykają aplikacji.
- **Menu Luny pod przyciskiem** – otwiera się równo pod burgerem; na niższych ekranach ma niższe kafelki zamiast wychodzić nad pasek.

## Co nowego w 1.0.14

**Połączone urządzenia** – Luna na komputerze i na telefonie łączy się bezpośrednio w tej samej sieci Wi-Fi, bez serwerów Luny i bez kont ([film](https://z4k0lzakol.github.io/Luna/#polaczenie)):

- **Parowanie kodem QR** – komputer: Ustawienia → Połączone urządzenia → Sparuj urządzenie; telefon: Menu → Urządzenia → Skanuj kod. Między komputerami – 6-cyfrowy kod.
- **Strona na drugim urządzeniu** – „Wyślij na urządzenie” w menu karty, linku i strony; karty otwarte na innych urządzeniach w menu.
- **Pliki bez utraty jakości** – zdjęcia, filmy i dokumenty bajt w bajt (jak LocalSend), także z „Udostępnij → Luna” na Androidzie; odbiorca widzi „Przyjmij / Odrzuć”, pliki trafiają do Pobrane/Luna.
- **Wspólne zakładki, kafelki i „Do przeczytania”** w domowej sieci, **jeden schowek**, **telefon jako pilot** do filmów na komputerze i **powiadomienia** z komputera na telefonie.
- Połączenie jest szyfrowane i **domyślnie wyłączone** – każdą funkcję wyłączysz osobno.

W 1.0.13: automatyczne aktualizacje na Linuksie i Androidzie oraz stały podpis aplikacji na Androida.

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
