"""Komputer na potrzeby testu zgodności z telefonem (mobile/test/link_test.dart).

Uruchamia luna_link.Link na losowym porcie (bez wykrywania), wypisuje w pierwszej linii JSON z kodem parowania,
potem każde zdarzenie jako JSON w osobnej linii. Kończy się po zamknięciu wejścia (stdin).
    python tests/link_peer.py <folder>
"""
import json
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import luna_link as L  # noqa: E402

folder = sys.argv[1] if len(sys.argv) > 1 else "."
os.makedirs(folder, exist_ok=True)
lock = threading.Lock()


def out(**d):
    with lock:
        print(json.dumps(d, ensure_ascii=False), flush=True)


class H(L.Handler):
    def features(self):
        return ["open", "tabs", "clip", "sync", "files", "remote", "notify"]

    def allowed(self, feature, peer):
        return True

    def on_paired(self, p):
        out(ev="paired", name=p["name"], type=p["type"])

    def on_open(self, p, url, title):
        out(ev="open", url=url, title=title)

    def get_tabs(self, p):
        return [{"url": "https://z-komputera.example.org/", "title": "Z komputera"}]

    def on_clip(self, p, text):
        out(ev="clip", text=text)

    def on_sync(self, p, payload):
        out(ev="sync", cols=sorted((payload.get("cols") or {}).keys()), tabs=len(payload.get("tabs") or []))
        return {"v": 1, "device": "pc", "name": "Komputer", "t": 2_000_000_000,
                "cols": {"bookmarks": [{"title": "Z komputera", "url": "https://bm.example.org", "folder": "Praca"}]},
                "mtime": {"bookmarks": 2_000_000_000}, "logins": [], "deleted": {},
                "tabs": [{"url": "https://karta.example.org", "title": "Karta"}]}

    def offer_files(self, sender, files):
        return list(range(len(files)))

    def files_dir(self):
        return os.path.join(folder, "odebrane")

    def on_files_done(self, sender, paths):
        out(ev="files", names=[os.path.basename(p) for p in paths],
            sizes=[os.path.getsize(p) for p in paths])

    def on_remote(self, p, cmd, value):
        out(ev="remote", cmd=cmd, value=value)

    def on_notify(self, p, title, body, kind):
        out(ev="notify", title=title, body=body)


link = L.Link(os.path.join(folder, "pc.json"), H(), name="Komputer testowy", port=0, discovery=False)
link.start()
d = L.Link.parse_pair_uri(link.pair_uri())
out(ev="ready", port=link.port, fp=link.fp, code=d["code"], id=link.id)


def commands():
    """Polecenia z testu: {"cmd": "open"|"clip"|"notify"|"files", ...} – komputer → telefon."""
    for line in sys.stdin:
        try:
            c = json.loads(line)
            pid = next(iter(link.peers()))
            p = link.peers()[pid]
            if c.get("addr"):
                link.state["peers"][pid].update(addr=c["addr"], port=c["port"])
            if c["cmd"] == "open":
                link.open_on(pid, c["url"], "z komputera")
            elif c["cmd"] == "clip":
                link.clip_to(pid, c["text"])
            elif c["cmd"] == "notify":
                link.notify(pid, c["title"], c.get("body", ""))
            elif c["cmd"] == "files":
                path = os.path.join(folder, c["name"])
                with open(path, "wb") as f:
                    f.write(bytes(range(256)) * c["kb"] * 4)
                out(ev="sent", n=link.send_files(pid, [path]), size=os.path.getsize(path), peer=p["name"])
            out(ev="done", cmd=c["cmd"])
        except Exception as e:   # błąd zgłaszany testowi zamiast cichego zakończenia
            out(ev="error", error=f"{type(e).__name__}: {e}")


commands()
link.stop()
