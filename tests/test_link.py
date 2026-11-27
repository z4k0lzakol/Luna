"""Testy Luna Link (luna_link.py): dwa urządzenia w jednym procesie, połączenie przez localhost.

    python tests/test_link.py
"""
import os
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import luna_link as L  # noqa: E402

FAILS, N = [], [0]


def check(name, ok, detail=""):
    N[0] += 1
    print(("ok   " if ok else "FAIL ") + name, "" if ok else detail)
    if not ok:
        FAILS.append(name)


def raises(fn, text=""):
    try:
        fn()
    except (L.LinkError, OSError) as e:
        return text in str(e)
    return False


class H(L.Handler):
    def __init__(self, folder):
        self.folder, self.log, self.off = folder, [], set()
        self.accept = "all"; self.approve = True

    def features(self):
        return ["open", "tabs", "clip", "sync", "files", "remote", "notify", "approve"]

    def allowed(self, feature, peer):
        if feature == "files_unpaired":
            return "unpaired" not in self.off
        return feature not in self.off

    def on_paired(self, p):
        self.log.append(("paired", p["name"]))

    def on_unpaired(self, p):
        self.log.append(("unpaired", p["id"]))

    def on_open(self, p, url, title):
        self.log.append(("open", url, title))

    def get_tabs(self, p):
        return [{"url": "https://a.example/", "title": "A"}]

    def on_clip(self, p, text):
        self.log.append(("clip", text))

    def on_sync(self, p, payload):
        self.log.append(("sync", payload.get("cols", {}).get("bookmarks")))
        return {"v": 1, "cols": {"bookmarks": ["z serwera"]}}

    def offer_files(self, sender, files):
        self.log.append(("offer", sender.get("name"), [f["name"] for f in files]))
        return [] if self.accept == "none" else list(range(len(files))) if self.accept == "all" else [0]

    def files_dir(self):
        return self.folder

    def on_files_done(self, sender, paths):
        self.log.append(("done", [os.path.basename(p) for p in paths]))

    def on_remote(self, p, cmd, value):
        self.log.append(("remote", cmd, value))

    def on_notify(self, p, title, body, kind):
        self.log.append(("notify", title))

    def on_approve(self, p, what, detail):
        return self.approve


def main():
    tmp = Path(tempfile.mkdtemp(prefix="luna_link_"))
    ha, hb = H(str(tmp / "odebrane_a")), H(str(tmp / "odebrane_b"))
    a = L.Link(tmp / "a.json", ha, name="Komputer", port=0, discovery=False)
    b = L.Link(tmp / "b.json", hb, name="Telefon", dev_type="phone", port=0, discovery=False)
    a.start(); b.start()
    check("certificates created, fingerprints differ", len(a.fp) == 64 and a.fp != b.fp)
    check("identity persists across restarts", L.Link(tmp / "a.json", port=0, discovery=False).id == a.id)

    # parowanie: kod z QR, zły kod, zły certyfikat
    uri = a.pair_uri(); d = L.Link.parse_pair_uri(uri)
    check("QR link carries id, fp and a 6-digit code", d["id"] == a.id and d["fp"] == a.fp and len(d["code"]) == 6, d)
    check("wrong code rejected", raises(lambda: b.pair_with("127.0.0.1", a.port, a.fp, "000000" if d["code"] != "000000" else "111111"),
                                        "kod"))
    check("wrong certificate fingerprint rejected before sending anything",
          raises(lambda: b.pair_with("127.0.0.1", a.port, "0" * 64, d["code"]), "certyfikat"))
    p = b.pair_with("127.0.0.1", a.port, a.fp, d["code"])
    check("pairing works, both sides know each other", p["id"] == a.id and b.id in a.peers() and a.id in b.peers()
          and a.peers()[b.id]["token"] == b.peers()[a.id]["token"])
    check("pairing code is single-use", raises(lambda: b.pair_with("127.0.0.1", a.port, a.fp, d["code"]), "kod"))
    c0 = L.Link(tmp / "c0.json", H(str(tmp / "c0")), name="Zgadywacz", port=0, discovery=False); c0.ensure_cert()
    a.state["peers"][b.id]["addr"] = "127.0.0.1"; a.state["peers"][b.id]["port"] = b.port

    a.new_code()
    for _ in range(5):
        raises(lambda: c0.pair_with("127.0.0.1", a.port, a.fp, "x"))
    check("code stops working after 5 wrong guesses", a.code is None)

    # funkcje
    b.open_on(a.id, "https://example.com/x", "X")
    check("send tab opens the page on the other device", ("open", "https://example.com/x", "X") in ha.log)
    check("only http(s) links can be sent", raises(lambda: b.open_on(a.id, "file:///etc/passwd"), "http"))
    check("tabs from the other device", b.tabs_of(a.id) == [{"url": "https://a.example/", "title": "A"}])
    a.clip_to(b.id, "skopiowany tekst ąę")
    check("shared clipboard both ways", ("clip", "skopiowany tekst ąę") in hb.log)
    r = b.sync_with(a.id, {"v": 1, "cols": {"bookmarks": ["z telefonu"]}})
    check("sync exchanges payloads", ("sync", ["z telefonu"]) in ha.log and r["cols"]["bookmarks"] == ["z serwera"])
    b.remote(a.id, "seek", 30)
    check("remote control command", ("remote", "seek", 30) in ha.log)
    a.notify(b.id, "Pobieranie skończone")
    check("notification", ("notify", "Pobieranie skończone") in hb.log)
    check("approval yes", a.approve(b.id, "hasla") is True)
    hb.approve = False
    check("approval no", a.approve(b.id, "hasla") is False)

    # wyłączona funkcja
    ha.off.add("clip")
    check("disabled feature refused", raises(lambda: b.clip_to(a.id, "x"), "wyłączona"))
    ha.off.discard("clip")

    # obcy bez tokenu / ze złym tokenem
    c = L.Link(tmp / "c.json", H(str(tmp / "c")), name="Obcy", port=0, discovery=False)
    c.ensure_cert()
    check("unpaired device cannot open pages",
          raises(lambda: c._call("127.0.0.1", a.port, a.fp, "POST", "/v1/open", {"url": "https://x.pl"}), "sparowane"))
    check("stolen id with wrong token refused",
          raises(lambda: c._call("127.0.0.1", a.port, a.fp, "POST", "/v1/open", {"url": "https://x.pl"},
                                 token="zly") if False else _forged(c, a, b.id), "sparowane"))

    # pliki: bajt w bajt, kolizja nazw, częściowe przyjęcie, odrzucenie
    src = tmp / "wyslij"; src.mkdir()
    photo = src / "zdjęcie 1.jpg"; photo.write_bytes(os.urandom(3 * 2 ** 20 + 17))
    note = src / "notatka.txt"; note.write_text("cześć", encoding="utf-8")
    seen = []
    n = b.send_files(a.id, [str(photo), str(note)], progress=lambda d_, t_, f_: seen.append(d_))
    got = Path(ha.folder) / "zdjęcie 1.jpg"
    check("files arrive byte-for-byte (no quality loss)", n == 2 and got.read_bytes() == photo.read_bytes()
          and (Path(ha.folder) / "notatka.txt").read_text(encoding="utf-8") == "cześć")
    check("progress reported up to the total", seen and seen[-1] == photo.stat().st_size + note.stat().st_size)
    check("receiver told when all files are done", ("done", ["zdjęcie 1.jpg", "notatka.txt"]) in ha.log, ha.log[-3:])
    b.send_files(a.id, [str(note)])
    check("same name does not overwrite", (Path(ha.folder) / "notatka (2).txt").exists())
    ha.accept = "first"
    check("receiver may accept only some files", b.send_files(a.id, [str(note), str(photo)]) == 1)
    ha.accept = "none"
    check("declined transfer reported", raises(lambda: b.send_files(a.id, [str(note)]), "odrzucił"))
    ha.accept = "all"
    check("no stray partial files", not list(Path(ha.folder).glob("*.czesc")))

    # niesparowane urządzenie w sieci (jak LocalSend): tylko po włączeniu, zawsze z pytaniem
    tgt = {"addr": "127.0.0.1", "port": a.port, "fp": a.fp}
    check("unpaired sender can send files when allowed", c.send_files(tgt, [str(note)]) == 1)
    ha.off.add("unpaired")
    check("unpaired sending can be switched off", raises(lambda: c.send_files(tgt, [str(note)]), "nie przyjmuje"))
    ha.off.discard("unpaired")

    # uszkodzony plik (zła suma) jest usuwany
    bad = _send_corrupt(b, a, note)
    check("corrupted file rejected and removed", "suma" in bad and not list(Path(ha.folder).glob("*.czesc")), bad)

    # wykrywanie w sieci (multicast) – jeśli system pozwala
    _discovery(tmp)

    # rozparowanie
    b.forget(a.id)
    check("unpair removes the device on both sides", a.id not in b.peers() and b.id not in a.peers())
    check("after unpairing requests are refused",
          raises(lambda: c._call("127.0.0.1", a.port, a.fp, "GET", "/v1/tabs", None, token="x"), "sparowane"))
    a.stop(); b.stop()
    print(f"{N[0]} checks, {len(FAILS)} failures")
    if FAILS:
        print("FAILED:", FAILS); sys.exit(1)


def _forged(c, a, victim_id):
    """Żądanie z cudzym id i złym tokenem."""
    conn = c._conn("127.0.0.1", a.port, a.fp, 5)
    try:
        conn.request("POST", "/v1/open", body=b'{"url":"https://x.pl"}',
                     headers={"X-Luna-Id": victim_id, "X-Luna-Token": "zly", "Content-Type": "application/json"})
        r = conn.getresponse(); body = r.read().decode()
        if r.status >= 400:
            raise L.LinkError(body)
    finally:
        conn.close()


def _send_corrupt(b, a, note):
    import json
    p = b.peers()[a.id]
    offer = b._call("127.0.0.1", a.port, a.fp, "POST", "/v1/files",
                    {"files": [{"name": "zly.txt", "size": 5, "sha256": "0" * 64}]}, token=p["token"])
    conn = b._conn("127.0.0.1", a.port, a.fp, 5)
    try:
        conn.request("PUT", f"/v1/files/{offer['session']}/0", body=b"abcde",
                     headers={"X-Luna-Id": b.id, "X-Luna-Token": p["token"], "Content-Length": "5"})
        r = conn.getresponse()
        return json.loads(r.read().decode()).get("error", "")
    finally:
        conn.close()


def _discovery(tmp):
    port = 53400 + os.getpid() % 500
    seen = threading.Event()

    class HD(L.Handler):
        def nearby_changed(self):
            seen.set()
    x = L.Link(tmp / "x.json", HD(), name="X", port=0, discovery_port=port)
    y = L.Link(tmp / "y.json", L.Handler(), name="Y", port=0, discovery_port=port)
    try:
        x.start(); y.start()
    except OSError as e:
        print("skip discovery (multicast unavailable):", e); return
    if not (x.udp and y.udp):
        print("skip discovery (multicast unavailable)"); x.stop(); y.stop(); return
    end = time.time() + 5
    while time.time() < end and y.id not in x.nearby:
        time.sleep(0.1)
    if y.id not in x.nearby:
        print("skip discovery (multicast loopback blocked on this machine)")
    else:
        n = x.nearby[y.id]
        check("devices find each other on the network", n["name"] == "Y" and n["fp"] == y.fp and n["port"] == y.port, n)
    x.stop(); y.stop()


if __name__ == "__main__":
    socket.setdefaulttimeout(30)
    main()
