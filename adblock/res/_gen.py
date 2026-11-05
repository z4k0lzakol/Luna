# Generator pustych zasobów binarnych (obrazy, cisza MP3) – czysty stdlib, deterministyczny.
# Uruchomienie: python -I adblock/res/_gen.py  (zapisuje pliki obok siebie; --check tylko porównuje)
# noop-1s.mp4 (VP9, fragmentowany MP4) i noop-1s.webm (VP8) nagrał MediaRecorder samego QtWebEngine
# (canvas.captureStream) – nie da się ich odtworzyć stdlibem, więc są trzymane jako gotowe pliki.
import os
import struct
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))


def gif_1x1():
    # GIF89a 1x1, przezroczysty (GCE: indeks 0 przezroczysty), 43 bajty
    return (b"GIF89a" + struct.pack("<HHBBB", 1, 1, 0x80, 0, 0) + b"\x00" * 6
            + b"\x21\xf9\x04\x01\x00\x00\x00\x00"
            + b"\x2c" + struct.pack("<HHHHB", 0, 0, 1, 1, 0)
            + b"\x02\x02\x44\x01\x00" + b"\x3b")


def png(w, h):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    raw = b"".join(b"\x00" + b"\x00\x00\x00\x00" * w for _ in range(h))  # RGBA, alfa 0
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b""))


def mp3_silence(frames):
    # MPEG-1 Layer III, 32 kbit/s, 32 kHz, mono, bez CRC: ramka = 144 bajty, side info = 0 -> cisza
    frame = b"\xff\xfb\x18\xc0" + b"\x00" * 140
    return frame * frames


def build():
    return {
        "1x1.gif": gif_1x1(),
        "2x2.png": png(2, 2),
        "3x2.png": png(3, 2),
        "32x32.png": png(32, 32),
        "noop-0.1s.mp3": mp3_silence(3),
        "noop-0.5s.mp3": mp3_silence(14),
    }


def main(argv):
    check = "--check" in argv
    bad = 0
    for name, data in build().items():
        p = os.path.join(HERE, name)
        if check:
            try:
                with open(p, "rb") as f:
                    same = f.read() == data
            except OSError:
                same = False
            print(("ok   " if same else "DIFF ") + name)
            bad += not same
        else:
            with open(p, "wb") as f:
                f.write(data)
            print("zapisano", name, len(data))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
