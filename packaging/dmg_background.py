"""Tło okna obrazu .dmg Luny (macOS): „przeciągnij do Aplikacji” i jak otworzyć Lunę bez podpisu Apple.

Użycie (w GitHub Actions, na macOS): python packaging/dmg_background.py dist/dmg-tlo
Tworzy tlo.png (660×480) i tlo@2x.png (1320×960); z nich `tiffutil -cathidpicheck` robi tlo.tiff dla ekranów Retina.
Rozmieszczenie ikon w oknie ustawia create-dmg (patrz release.yml) – współrzędne poniżej muszą się z nim zgadzać.
"""
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 660, 480
APP_X, LINK_X, ICON_Y = 165, 495, 150    # środki ikon Luna.app i skrótu Aplikacje (create-dmg --icon / --app-drop-link)
HELP_Y = 400                              # plik „Jak otworzyć Lunę.txt” na środku pod tekstem (create-dmg --icon)
BG, FG, MUTED, ACCENT = (17, 17, 19), (243, 239, 230), (160, 156, 148), (201, 201, 201)

FONTS = ["/System/Library/Fonts/SFNS.ttf", "/System/Library/Fonts/Helvetica.ttc",
         "/Library/Fonts/Arial Unicode.ttf", "C:/Windows/Fonts/segoeui.ttf", "DejaVuSans.ttf"]


def font(size):
    for f in FONTS:
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def center(d, y, text, f, fill):
    w = d.textlength(text, font=f)
    d.text(((d.im.size[0] - w) / 2, y), text, font=f, fill=fill)


def render(scale):
    img = Image.new("RGB", (W * scale, H * scale), BG)
    d = ImageDraw.Draw(img)
    s = lambda v: int(v * scale)
    rnd = random.Random(7)                       # nocne niebo – te same gwiazdy przy każdym budowaniu
    for _ in range(70):
        x, y, r = rnd.uniform(0, W), rnd.uniform(0, H), rnd.choice([0.6, 0.8, 1.0, 1.3])
        c = rnd.randint(70, 150)
        if (y < 62 and 150 < x < 510) or 248 < y < 372:   # bez gwiazd pod napisami
            continue
        d.ellipse([s(x - r), s(y - r), s(x + r), s(y + r)], fill=(c, c, c - 6))

    center(d, s(26), "Przeciągnij Lunę do Aplikacji", font(s(20)), FG)
    # strzałka między ikonami
    y, x0, x1 = s(ICON_Y), s(APP_X + 62), s(LINK_X - 62)
    d.line([x0, y, x1 - s(10), y], fill=ACCENT, width=s(3))
    d.polygon([(x1, y), (x1 - s(14), y - s(8)), (x1 - s(14), y + s(8))], fill=ACCENT)

    f, fb = font(s(13)), font(s(14))
    lines = [("Pierwsze uruchomienie", fb, FG),
             ("Luna nie ma jeszcze podpisu Apple, więc macOS za pierwszym razem napisze,", f, MUTED),
             ("że „Luna” nie została otwarta. Kliknij Gotowe, potem wejdź w", f, MUTED),
             ("Ustawienia systemowe → Prywatność i ochrona → Otwórz mimo to.", fb, FG),
             ("Wystarczy raz – kolejne wersje Luna pobiera i instaluje sama.", f, MUTED)]
    y = s(250)
    for text, ff, col in lines:
        center(d, y, text, ff, col); y += s(21 if ff is fb else 19)
    return img


def main(out):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    render(1).save(out / "tlo.png", dpi=(72, 72))
    render(2).save(out / "tlo@2x.png", dpi=(144, 144))
    print(f"Tło .dmg w {out}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "dist/dmg-tlo")
