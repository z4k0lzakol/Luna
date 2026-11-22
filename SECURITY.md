# Zasady bezpieczeństwa

## Wspierane wersje

Poprawki bezpieczeństwa trafiają do najnowszej wersji z gałęzi `main`. Luna pobrana przez `git clone` aktualizuje się sama (Ustawienia → Aktualizacje) – korzystaj zawsze z najnowszej wersji.

| Wersja | Poprawki bezpieczeństwa |
|---|---|
| najnowsza z `main` | <img src="docs/img/ikony/tak.svg" width="16" height="16" alt="tak"> |
| starsze | <img src="docs/img/ikony/nie.svg" width="16" height="16" alt="nie"> zaktualizuj Lunę |

Luna wyświetla strony silnikiem Chromium z biblioteki Qt WebEngine. Poprawki samego silnika przychodzą z aktualizacją pakietu `PyQt6-WebEngine`:

```bash
python -m pip install --upgrade PyQt6 PyQt6-WebEngine
```

## Jak zgłosić lukę

**Nie opisuj luki w publicznym zgłoszeniu (issue).**

Zgłoś ją prywatnie przez formularz GitHuba: [**Report a vulnerability**](https://github.com/z4k0lzakol/Luna/security/advisories/new) (zakładka *Security* w repozytorium). Zgłoszenie widzi tylko opiekun projektu.

Opisz, jeśli możesz:

- czego dotyczy luka (np. menedżer haseł, blokada reklam, obsługa stron, aktualizacje),
- jak ją odtworzyć – kroki albo przykładowa strona,
- jakie mogą być skutki,
- wersję Luny (Pomoc → O Lunie) i system.

## Co dalej

- Potwierdzenie otrzymania zgłoszenia – zwykle w ciągu **7 dni**.
- Ocena i plan poprawki – zwykle w ciągu **30 dni**, szybciej przy poważnych lukach.
- Po wydaniu poprawki opiszemy lukę w zgłoszeniu bezpieczeństwa i – jeśli chcesz – podziękujemy Ci z imienia lub pseudonimu.

Prosimy o nieujawnianie szczegółów luki, dopóki poprawka nie będzie dostępna.

## Zakres

Zgłoszenia dotyczą kodu Luny w tym repozytorium. Luki w samym Chromium, Qt albo w stronach i usługach zewnętrznych zgłaszaj ich twórcom (np. [Chromium](https://www.chromium.org/Home/chromium-security/reporting-security-bugs/), [Qt](https://www.qt.io/product/security)).

---

**English:** Please report vulnerabilities privately via [GitHub's private vulnerability reporting](https://github.com/z4k0lzakol/Luna/security/advisories/new) – not in public issues. Only the latest version from `main` receives security fixes. We aim to acknowledge reports within 7 days.
