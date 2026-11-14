# Podpis cyfrowy Luny przez SignPath Foundation – co zrobić

SignPath Foundation podpisuje za darmo wydania projektów open source. Zgłoszenie musi złożyć właściciel projektu (Ty) – chodzi o Twoją tożsamość jako wydawcy.

## Twoje kroki

1. **Włącz uwierzytelnianie dwuskładnikowe (2FA) na GitHubie** – SignPath tego wymaga od wszystkich członków zespołu: GitHub → Settings → Password and authentication → Two-factor authentication.
2. **Złóż zgłoszenie**: https://signpath.org/apply – odpowiedzi do wklejenia są niżej (po angielsku, bo formularz jest po angielsku). Odpowiadaj zgodnie z prawdą; jeśli formularz pyta o coś, czego tu nie ma, odpowiedz krótko i rzeczowo.
3. **Poczekaj na odpowiedź** – SignPath rozpatruje projekty ręcznie i może odmówić bez podania przyczyny.
4. **Po akceptacji** (w panelu SignPath i na GitHubie):
   - załóż w SignPath konto z 2FA, w projekcie dodaj system budowania „GitHub.com” i zainstaluj aplikację https://github.com/apps/signpath w repozytorium Luny,
   - wgraj konfiguracje artefaktów z tego folderu: `luna-exe.xml` (slug `luna-exe`) i `luna-setup.xml` (slug `luna-setup`),
   - w repozytorium GitHub (Settings → Secrets and variables → Actions) dodaj:
     - sekret `SIGNPATH_API_TOKEN` (token API z SignPath, rola „submitter”),
     - zmienne `SIGNPATH_ORGANIZATION_ID`, `SIGNPATH_PROJECT_SLUG`, `SIGNPATH_SIGNING_POLICY_SLUG`.
5. **Od tej chwili** przy każdym wydaniu (tag `v…`) GitHub wyśle `Luna.exe` i instalator do podpisu; zatwierdzasz je w panelu SignPath (to wymóg SignPath – każde wydanie ręcznie). Bez tych ustawień budowanie działa jak dotąd, bez podpisu.

Zasady podpisywania („Code signing policy”) są już na stronie Luny (https://z4k0lzakol.github.io/Luna/#podpis) i w README – SignPath tego wymaga.

## Rzecz do wyjaśnienia

Warunki SignPath mówią o licencji OSI „without commercial dual-licensing for all components”. Luna jest na GPL v3, ale korzysta z PyQt6 (GPL v3 **albo** licencja komercyjna Riverbank) i Qt (LGPL/GPL **albo** komercyjna). Nie wiadomo, czy SignPath uznaje to za problem – warto o to zapytać w zgłoszeniu (pole z uwagami), zamiast to pomijać.

---

## Odpowiedzi do formularza (English)

**Project name:** Luna

**Repository:** https://github.com/z4k0lzakol/Luna

**Homepage / download page:** https://z4k0lzakol.github.io/Luna/ (downloads: https://github.com/z4k0lzakol/Luna/releases/latest)

**License:** GPL-3.0-only (LICENSE file in the repository). Additional term under GPLv3 section 7: the name and logo "Luna" are not licensed for modified versions.

**Short description:**
Luna is a free, open-source desktop web browser for Windows, Linux and macOS, written in Python with PyQt6 / Qt WebEngine (Chromium). It focuses on privacy and productivity: built-in ad and tracker blocking, split screen with 2–3 pages, profiles, home-screen tiles and widgets, reader mode, translation, a side panel for AI chat services and messengers, an encrypted local password manager and a first-run guide. It has no accounts, no telemetry and no servers of its own; all user data stays on the user's computer. The UI is in Polish.

**What should be signed:**
Windows release binaries built by GitHub Actions on GitHub-hosted runners from this repository (`.github/workflows/release.yml`): the application launcher `Luna.exe` (PyInstaller) and the Inno Setup installer `Luna-<version>-Windows-Setup.exe`. Third-party upstream binaries bundled by PyInstaller (Qt, PyQt6, Python runtime) are included unmodified and are not signed by us.

**Why signing is needed:**
Windows 11 Smart App Control blocks unsigned downloaded programs entirely (there is no "run anyway"), so users with Smart App Control enabled currently cannot run Luna releases at all. SmartScreen also warns on every unsigned release.

**Build process:**
Fully automated: a version tag `v*` triggers the GitHub Actions workflow, which builds with PyInstaller on Windows, Linux and macOS, runs a start-up smoke test of each build (and an install / launch / uninstall test of the Windows installer), and publishes a GitHub release. The signing steps are already prepared in the workflow (`signpath/github-action-submit-signing-request@v3`) and activate once the SignPath secrets are configured. Every release will be approved manually.

**Team / roles:**
One-person project. Single maintainer: z4k0lzakol (author, committer, reviewer and approver). The code is largely written with AI assistance ("vibecoded" with Claude) under the maintainer's direction; all changes are tested automatically and every release is built and smoke-tested on GitHub-hosted runners. Pull requests from others are reviewed before merging. GitHub and SignPath accounts use multi-factor authentication.

**Code signing policy:** https://z4k0lzakol.github.io/Luna/#podpis (also in README.md, section "Code signing policy")

**Privacy policy:** https://z4k0lzakol.github.io/Luna/privacy.html – lists every third-party service the browser contacts, what is sent and how to disable it; the installer and the first-run guide show a privacy summary.

**Uninstallation:** standard Windows uninstall entry (installer and in-app installation); user data is kept in the user's profile folder.

**Notes / question:**
Luna itself is GPL-3.0. It depends on PyQt6 (GPL-3.0 or Riverbank commercial license) and Qt (LGPL-3.0/GPL or commercial). We use these only under their open-source licenses and do not offer any commercial licensing of Luna. Please let us know if the dual licensing of these upstream libraries is an issue for the "no commercial dual-licensing" condition.
