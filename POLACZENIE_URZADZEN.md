# Połączenie urządzeń Luny (Luna Link)

Luna na komputerze i na telefonie łączy się **bezpośrednio w sieci lokalnej** (ta sama Wi-Fi) – bez serwerów Luny i bez kont.
Poza domem dane przechodzą przez zaszyfrowany folder w chmurze (Synchronizacja), tak jak dotąd między komputerami.

Ten plik opisuje protokół – wspólny dla `luna_link.py` (komputer) i `mobile/lib/link/` (telefon).

## Tożsamość urządzenia

Każde urządzenie ma:

| pole | opis |
|---|---|
| `id` | losowe 16 znaków hex, stałe |
| `name` | nazwa widoczna dla innych („Laptop Kaspra”, „Pixel 8”) |
| `type` | `desktop` / `phone` / `tablet` |
| certyfikat TLS | samopodpisany, klucz EC P-256, ważny 20 lat |
| `fp` | odcisk certyfikatu: SHA-256 z DER, hex małymi literami |

Połączenia są przez **HTTPS z przypiętym certyfikatem**: klient nie sprawdza urzędu certyfikacji, tylko porównuje `fp`
z zapisanym (urządzenie sparowane) albo z ogłoszonym w sieci (niesparowane, jak w LocalSend).

## Wykrywanie (UDP multicast)

- grupa `224.0.0.167`, port **53318**; serwer HTTPS na porcie **53317** (gdy zajęty – kolejny wolny, podany w ogłoszeniu)
- ogłoszenie (JSON, UTF-8): `{"luna": 1, "id", "name", "type", "port", "fp", "reply": false}`
- przy starcie i co 30 s; po odebraniu cudzego ogłoszenia z `"reply": false` urządzenie odpowiada swoim (`"reply": true`)
- urządzenie znika z listy po 90 s bez ogłoszenia
- dodatkowo: sparowane urządzenia pamiętają ostatni adres i próbują go bezpośrednio (`GET /v1/info`)

## Parowanie

Sparowanie daje obu stronom wspólny **token** (32 bajty, base64url) – dowód przy każdym żądaniu.

1. Urządzenie A pokazuje **kod QR** i **6-cyfrowy kod** (ważne 5 minut, jednorazowe).
   QR: `luna://pair?d=<base64url JSON>` z `{"v": 1, "id", "name", "type", "ips": [...], "port", "fp", "code"}`.
2. Urządzenie B skanuje QR (telefon) albo wybiera A z listy wykrytych i wpisuje kod (komputer).
3. B → A: `POST /v1/pair` `{"id", "name", "type", "fp", "port", "code"}` (połączenie przypięte do `fp` A).
4. A sprawdza kod, zapisuje B i odpowiada `{"token", "id", "name", "type", "fp"}`. B zapisuje A.

Usunięcie urządzenia po jednej stronie: `POST /v1/unpair` – druga strona też je usuwa.

## Żądania

Nagłówki każdego żądania: `X-Luna-Id: <id nadawcy>`, a od sparowanych także `X-Luna-Token: <token>`.
Odpowiedzi JSON; błąd: `{"error": "opis po polsku"}` z kodem 4xx.

| żądanie | kto może | opis |
|---|---|---|
| `GET /v1/info` | każdy | `{"luna": 1, "id", "name", "type", "fp", "features": [...]}` |
| `POST /v1/pair`, `POST /v1/unpair` | patrz wyżej | parowanie |
| `POST /v1/open` `{"url", "title"}` | sparowane | otwórz stronę na tym urządzeniu (2) |
| `GET /v1/tabs` | sparowane | `{"tabs": [{"url", "title"}]}` – otwarte karty (3) |
| `POST /v1/clip` `{"text"}` | sparowane | wspólny schowek (6) |
| `POST /v1/sync` | sparowane | wymiana danych (4, 7, 12, 13, 14) – patrz niżej |
| `POST /v1/files` `{"files": [{"name", "size", "sha256", "type"}]}` | każdy* | prośba o przesłanie plików (9) |
| `PUT /v1/files/<sesja>/<nr>` | z sesji | treść pliku bez zmian (bajt w bajt) |
| `POST /v1/remote` `{"cmd", "value"}` | sparowane | pilot: `playpause`, `seek`, `volume`, `next_tab`, `prev_tab` (8) |
| `POST /v1/notify` `{"title", "body", "kind"}` | sparowane | powiadomienie (11) |
| `POST /v1/approve` `{"what", "detail"}` | sparowane | prośba o zatwierdzenie na telefonie (10) → `{"ok": bool}` |

\* niesparowane urządzenie może wysłać pliki tylko gdy odbiorca to włączył („Odbieraj pliki od urządzeń w tej sieci”);
odbiorca zawsze widzi pytanie „Przyjmij / Odrzuć”. Sparowane – według ustawienia („pytaj” albo „przyjmuj od razu”).

### Pliki (9)

1. `POST /v1/files` → odbiorca pyta użytkownika → `{"session", "accept": [nr, ...]}` albo 403 (odrzucone).
2. Dla każdego przyjętego pliku `PUT /v1/files/<sesja>/<nr>` z treścią (`Content-Length` = rozmiar).
   Odbiorca liczy SHA-256 i porównuje z zapowiedzianym; niezgodny plik jest usuwany.
3. Pliki trafiają do folderu Pobrane / `Luna` z oryginalną nazwą (przy kolizji: `nazwa (2).ext`). Zdjęcia i filmy
   bez przetwarzania – ta sama jakość i metadane.

### Synchronizacja w sieci (4, 7, 12, 13, 14)

`POST /v1/sync` – ciało to **ładunek synchronizacji** (ten sam format co plik `.lunasync` w folderze chmury, bez szyfrowania
hasłem – chroni go TLS):

```json
{"v": 1, "device", "name", "t", "cols": {...}, "mtime": {...}, "logins": [...], "deleted": {...}, "tabs": [...]}
```

Odbiorca scala ładunek („nowsza kolekcja wygrywa”, hasła wpis po wpisie) i odpowiada swoim ładunkiem, który nadawca też scala.
Kolekcje: `tiles`, `bookmarks`, `highlights`, `readlater`, `addresses`, `settings`, a od Luna Link także
`widgets` (zadania, notatki – 13), `workspaces` (14), `progress` (miejsce czytania i oglądania – 12).
Każda kolekcja i hasła trafiają do ładunku tylko gdy ich synchronizacja jest włączona po obu stronach.

## Ustawienia (wszystko da się wyłączyć)

Ustawienia → Połączone urządzenia: główny przełącznik (domyślnie **wyłączony** – Luna nie ogłasza się w sieci i nie nasłuchuje,
dopóki użytkownik sam nie włączy połączenia albo nie zacznie parowania) oraz osobno: odbieranie stron, karty z innych urządzeń, wspólny schowek, synchronizacja (każda kolekcja), hasła,
pliki (i od niesparowanych), pilot, powiadomienia, zatwierdzanie na telefonie.
