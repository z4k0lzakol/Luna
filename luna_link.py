"""Luna Link – połączenie urządzeń Luny w sieci lokalnej (komputer ↔ telefon ↔ komputer), bez serwerów Luny.

Protokół: POLACZENIE_URZADZEN.md. Ten moduł nie zależy od Qt – interfejs Luny podaje obiekt `handler` z metodami
wywoływanymi z wątków serwera (patrz klasa Handler). Wymaga pakietu `cryptography` (certyfikat TLS urządzenia); bez niego
`available()` zwraca False i Luna działa dalej bez połączenia urządzeń.
"""
import base64
import hashlib
import http.client
import ipaddress
import json
import os
import re
import secrets
import socket
import ssl
import struct
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

GROUP, DISCOVERY_PORT, HTTP_PORT = "224.0.0.167", 53318, 53317
ANNOUNCE_EVERY, NEARBY_TTL = 30, 90
CODE_TTL = 300
MAX_JSON = 64 * 2 ** 20            # ładunek synchronizacji (z kopią offline „Do przeczytania”)
CHUNK = 1 << 20


def available():
    try:
        import cryptography  # noqa: F401
        return True
    except ImportError:
        return False


def b64u(b):
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def unb64u(s):
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def fingerprint(der):
    return hashlib.sha256(der).hexdigest()


def make_cert(dev_id):
    """(cert PEM, klucz PEM) – samopodpisany certyfikat urządzenia, EC P-256, 20 lat."""
    import datetime
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, f"Luna {dev_id}")])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name).public_key(key.public_key())
            .serial_number(x509.random_serial_number()).not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=365 * 20)).sign(key, hashes.SHA256()))
    return (cert.public_bytes(serialization.Encoding.PEM).decode(),
            key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                              serialization.NoEncryption()).decode())


def local_ips():
    """Adresy IPv4 tego komputera w sieciach lokalnych (pierwszy – używany do wyjścia na świat)."""
    ips = []
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("10.255.255.255", 1))   # nic nie jest wysyłane – system tylko wybiera interfejs
        ips.append(s.getsockname()[0]); s.close()
    except OSError:
        pass
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            ips.append(info[4][0])
    except OSError:
        pass
    out = []
    for ip in ips:
        try:
            a = ipaddress.ip_address(ip)
        except ValueError:
            continue
        if a.is_private and not a.is_loopback and ip not in out:
            out.append(ip)
    return out


def safe_name(name):
    name = re.sub(r'[\x00-\x1f<>:"/\\|?*]', "_", os.path.basename(str(name or "plik"))).strip(" .") or "plik"
    return name[:180]


def unique_path(folder, name):
    p = Path(folder) / safe_name(name)
    if not p.exists():
        return p
    stem, suf = p.stem, p.suffix
    for i in range(2, 10000):
        q = p.with_name(f"{stem} ({i}){suf}")
        if not q.exists():
            return q
    return p.with_name(f"{stem} ({secrets.token_hex(3)}){suf}")


class LinkError(Exception):
    pass


class Handler:
    """Wywołania z wątków serwera. Luna nadpisuje to, co obsługuje; reszta odmawia."""

    def features(self):
        return []

    def allowed(self, feature, peer):          # przełączniki w ustawieniach
        return False

    def on_paired(self, peer):
        pass

    def on_unpaired(self, peer):
        pass

    def on_open(self, peer, url, title):
        pass

    def get_tabs(self, peer):
        return []

    def on_clip(self, peer, text):
        pass

    def on_sync(self, peer, payload):          # → własny ładunek
        return {}

    def offer_files(self, sender, files):      # → lista przyjętych numerów (pyta użytkownika, blokuje)
        return []

    def files_dir(self):
        return str(Path.home() / "Downloads" / "Luna")

    def on_file(self, sender, path, meta):
        pass

    def on_files_done(self, sender, paths):
        pass

    def on_remote(self, peer, cmd, value):
        pass

    def on_notify(self, peer, title, body, kind):
        pass

    def on_approve(self, peer, what, detail):  # → bool (pyta użytkownika, blokuje)
        return False

    def nearby_changed(self):
        pass


class Link:
    def __init__(self, state_path, handler=None, name="Komputer", dev_type="desktop", port=HTTP_PORT,
                 discovery=True, discovery_port=DISCOVERY_PORT):
        self.path = Path(state_path); self.h = handler or Handler()
        self.port_wanted, self.discovery, self.discovery_port = port, discovery, discovery_port
        self.lock = threading.RLock()
        self.state = self._load()
        st = self.state
        st.setdefault("id", secrets.token_hex(8)); st.setdefault("name", name); st.setdefault("type", dev_type)
        st.setdefault("peers", {})
        self.nearby = {}                       # id → {name, type, fp, addr, port, seen}
        self.code = None                       # (kod, ważny do)
        self.sessions = {}                     # przesyłanie plików
        self.httpd = self.udp = None; self.port = None; self._stop = threading.Event()
        self._threads = []

    # --- stan ---
    def _load(self):
        try:
            d = json.loads(self.path.read_text(encoding="utf-8"))
            return d if isinstance(d, dict) else {}
        except (OSError, ValueError):
            return {}

    def save(self):
        with self.lock:
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.state, ensure_ascii=False, indent=1), encoding="utf-8")
            try:
                os.chmod(tmp, 0o600)
            except OSError:
                pass
            tmp.replace(self.path)

    @property
    def id(self):
        return self.state["id"]

    @property
    def name(self):
        return self.state["name"]

    def set_name(self, name):
        self.state["name"] = (name or "").strip()[:60] or self.state["name"]; self.save(); self.announce()

    @property
    def fp(self):
        return self.state.get("fp", "")

    def peers(self):
        with self.lock:
            return {k: dict(v, id=k) for k, v in self.state["peers"].items()}

    def peer(self, pid):
        p = self.state["peers"].get(pid)
        return dict(p, id=pid) if p else None

    def info(self):
        return {"luna": 1, "id": self.id, "name": self.name, "type": self.state["type"], "fp": self.fp,
                "port": self.port or self.port_wanted, "features": self.h.features()}

    # --- start / stop ---
    def ensure_cert(self):
        if not (self.state.get("cert") and self.state.get("key")):
            self.state["cert"], self.state["key"] = make_cert(self.id)
            self.save()
        der = ssl.PEM_cert_to_DER_cert(self.state["cert"])
        if self.state.get("fp") != fingerprint(der):
            self.state["fp"] = fingerprint(der); self.save()

    def _server_ctx(self):
        import tempfile
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        # load_cert_chain przyjmuje tylko pliki – krótko w pliku tymczasowym, potem usuwany
        fd, p = tempfile.mkstemp(suffix=".pem")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                f.write(self.state["cert"] + "\n" + self.state["key"])
            ctx.load_cert_chain(p)
        finally:
            try:
                os.remove(p)
            except OSError:
                pass
        return ctx

    def running(self):
        return self.httpd is not None

    def start(self):
        if self.httpd:
            return True
        self.ensure_cert(); self._stop.clear()
        link = self

        class Srv(ThreadingHTTPServer):
            daemon_threads = True
            allow_reuse_address = False

        srv = None
        ports = [0] if not self.port_wanted else [self.port_wanted] + list(range(self.port_wanted + 1, self.port_wanted + 20)) + [0]
        for port in ports:
            try:
                srv = Srv(("0.0.0.0", port), _make_req_handler(link)); break
            except OSError:
                continue
        if srv is None:
            raise LinkError("nie udało się otworzyć portu")
        srv.socket = self._server_ctx().wrap_socket(srv.socket, server_side=True)
        self.httpd = srv; self.port = srv.server_address[1]
        t = threading.Thread(target=srv.serve_forever, daemon=True, name="luna-link-http"); t.start(); self._threads.append(t)
        if self.discovery:
            try:
                self._start_discovery()
            except OSError:
                self.udp = None
        return True

    def stop(self):
        self._stop.set()
        if self.httpd:
            try:
                self.httpd.shutdown(); self.httpd.server_close()
            except OSError:
                pass
            self.httpd = None
        if self.udp:
            try:
                self.udp.close()
            except OSError:
                pass
            self.udp = None
        self.nearby.clear()

    # --- wykrywanie ---
    def _start_discovery(self):
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if hasattr(socket, "SO_REUSEPORT"):
            try:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEPORT, 1)
            except OSError:
                pass
        s.bind(("", self.discovery_port))
        mreq = struct.pack("4sl", socket.inet_aton(GROUP), socket.INADDR_ANY)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
        s.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 1)
        s.settimeout(1.0); self.udp = s
        for fn in (self._listen, self._announce_loop):
            t = threading.Thread(target=fn, daemon=True, name="luna-link-udp"); t.start(); self._threads.append(t)

    def _packet(self, reply=False):
        return json.dumps({"luna": 1, "id": self.id, "name": self.name, "type": self.state["type"],
                           "port": self.port, "fp": self.fp, "reply": reply}).encode("utf-8")

    def announce(self, reply=False):
        if not self.udp:
            return
        try:
            self.udp.sendto(self._packet(reply), (GROUP, self.discovery_port))
        except OSError:
            pass

    def _announce_loop(self):
        while not self._stop.is_set():
            self.announce()
            gone = [k for k, v in self.nearby.items() if time.time() - v["seen"] > NEARBY_TTL]
            for k in gone:
                self.nearby.pop(k, None)
            if gone:
                self.h.nearby_changed()
            self._stop.wait(ANNOUNCE_EVERY)

    def _listen(self):
        while not self._stop.is_set() and self.udp:
            try:
                data, (addr, _) = self.udp.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                break
            try:
                d = json.loads(data.decode("utf-8"))
            except ValueError:
                continue
            if not isinstance(d, dict) or d.get("luna") != 1 or d.get("id") in (None, self.id):
                continue
            self.saw(d["id"], d.get("name", "?"), d.get("type", "desktop"), d.get("fp", ""), addr, int(d.get("port") or HTTP_PORT))
            if not d.get("reply"):
                self.announce(reply=True)

    def saw(self, pid, name, dev_type, fp, addr, port):
        new = pid not in self.nearby
        self.nearby[pid] = {"id": pid, "name": str(name)[:60], "type": dev_type, "fp": fp, "addr": addr, "port": port,
                            "seen": time.time(), "paired": pid in self.state["peers"]}
        p = self.state["peers"].get(pid)
        if p and p.get("fp") == fp and (p.get("addr"), p.get("port")) != (addr, port):
            p["addr"], p["port"] = addr, port; self.save()
        if new:
            self.h.nearby_changed()

    # --- parowanie ---
    def new_code(self):
        self.code = (f"{secrets.randbelow(10 ** 6):06d}", time.time() + CODE_TTL); self.code_fails = 0
        return self.code[0]

    def pair_uri(self):
        code = self.code[0] if self.code and self.code[1] > time.time() else self.new_code()
        d = {"v": 1, "id": self.id, "name": self.name, "type": self.state["type"], "ips": local_ips(),
             "port": self.port, "fp": self.fp, "code": code}
        return "luna://pair?d=" + b64u(json.dumps(d, separators=(",", ":")).encode())

    @staticmethod
    def parse_pair_uri(uri):
        m = re.match(r"luna://pair\?d=([A-Za-z0-9_-]+)$", (uri or "").strip())
        if not m:
            raise LinkError("to nie jest kod parowania Luny")
        return json.loads(unb64u(m.group(1)))

    def _accept_pair(self, d):
        code = str(d.get("code", ""))
        if not (self.code and self.code[1] > time.time() and secrets.compare_digest(code, self.code[0])):
            self.code_fails = getattr(self, "code_fails", 0) + 1
            if self.code_fails >= 5:   # zgadywanie kodu: po 5 próbach kod przestaje działać
                self.code = None
            raise LinkError("zły albo nieważny kod parowania")
        if not (re.fullmatch(r"[0-9a-f]{16}", str(d.get("id", ""))) and re.fullmatch(r"[0-9a-f]{64}", str(d.get("fp", "")))):
            raise LinkError("niepoprawne dane urządzenia")
        self.code = None   # jednorazowy
        token = b64u(secrets.token_bytes(32))
        peer = {"name": str(d.get("name", "?"))[:60], "type": d.get("type", "phone"), "fp": d["fp"], "token": token,
                "addr": d.get("_addr"), "port": int(d.get("port") or HTTP_PORT), "since": int(time.time())}
        with self.lock:
            self.state["peers"][d["id"]] = peer; self.save()
        self.h.on_paired(dict(peer, id=d["id"]))
        return {"token": token, "id": self.id, "name": self.name, "type": self.state["type"], "fp": self.fp}

    def pair_with(self, addr, port, fp, code):
        """Sparuj się z urządzeniem pokazującym kod (adres z QR albo z listy wykrytych)."""
        body = {"id": self.id, "name": self.name, "type": self.state["type"], "fp": self.fp, "port": self.port, "code": code}
        r = self._call(addr, port, fp, "POST", "/v1/pair", body, token=None)
        if r.get("fp") != fp or not r.get("token"):
            raise LinkError("urządzenie odpowiedziało niepoprawnie")
        peer = {"name": str(r.get("name", "?"))[:60], "type": r.get("type", "desktop"), "fp": fp, "token": r["token"],
                "addr": addr, "port": int(port), "since": int(time.time())}
        with self.lock:
            self.state["peers"][r["id"]] = peer; self.save()
        if r["id"] in self.nearby:
            self.nearby[r["id"]]["paired"] = True
        self.h.on_paired(dict(peer, id=r["id"]))
        return dict(peer, id=r["id"])

    def pair_from_uri(self, uri):
        d = self.parse_pair_uri(uri); last = None
        for ip in d.get("ips") or []:
            try:
                return self.pair_with(ip, int(d["port"]), d["fp"], d["code"])
            except (LinkError, OSError) as e:
                last = e
        raise LinkError(f"nie udało się połączyć z „{d.get('name', '?')}” ({last})")

    def forget(self, pid, tell=True):
        p = self.peer(pid)
        if not p:
            return
        if tell:
            try:
                self.request(pid, "POST", "/v1/unpair", {}, timeout=4)
            except (LinkError, OSError):
                pass
        with self.lock:
            self.state["peers"].pop(pid, None); self.save()
        if pid in self.nearby:
            self.nearby[pid]["paired"] = False
        self.h.on_unpaired(p)

    def rename_peer(self, pid, name):
        with self.lock:
            if pid in self.state["peers"]:
                self.state["peers"][pid]["name"] = name[:60]; self.save()

    # --- klient ---
    def _conn(self, addr, port, fp, timeout):
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        c = http.client.HTTPSConnection(addr, int(port), context=ctx, timeout=timeout)
        c.connect()
        der = c.sock.getpeercert(binary_form=True)
        if not der or not secrets.compare_digest(fingerprint(der), fp or ""):
            c.close(); raise LinkError("certyfikat urządzenia się nie zgadza – połączenie przerwane")
        return c

    def _headers(self, token, extra=None):
        h = {"X-Luna-Id": self.id, "User-Agent": "Luna-Link/1"}
        if token:
            h["X-Luna-Token"] = token
        h.update(extra or {})
        return h

    def _call(self, addr, port, fp, method, path, body=None, token=None, timeout=10):
        c = self._conn(addr, port, fp, timeout)
        try:
            data = json.dumps(body or {}, ensure_ascii=False).encode("utf-8") if body is not None else None
            c.request(method, path, body=data, headers=self._headers(token, {"Content-Type": "application/json"}))
            r = c.getresponse(); raw = r.read(MAX_JSON + 1)
            try:
                d = json.loads(raw.decode("utf-8") or "{}")
            except ValueError:
                d = {}
            if r.status >= 400:
                raise LinkError(d.get("error") or f"błąd {r.status}")
            return d
        finally:
            c.close()

    def addresses(self, pid):
        """Adresy do wypróbowania: z ostatniego ogłoszenia, potem zapamiętany."""
        p = self.state["peers"].get(pid) or {}; out = []
        n = self.nearby.get(pid)
        if n and n.get("fp") == p.get("fp"):
            out.append((n["addr"], n["port"]))
        if p.get("addr") and (p["addr"], p.get("port")) not in out:
            out.append((p["addr"], p.get("port") or HTTP_PORT))
        return out

    def reachable(self, pid):
        return pid in self.nearby

    def request(self, pid, method, path, body=None, timeout=10):
        p = self.state["peers"].get(pid)
        if not p:
            raise LinkError("urządzenie nie jest sparowane")
        last = LinkError("urządzenie nie jest w tej sieci")
        for addr, port in self.addresses(pid):
            try:
                r = self._call(addr, port, p["fp"], method, path, body, token=p["token"], timeout=timeout)
                if (p.get("addr"), p.get("port")) != (addr, port):
                    with self.lock:
                        p["addr"], p["port"] = addr, port; self.save()
                return r
            except (OSError, ssl.SSLError) as e:
                last = e
        raise last if isinstance(last, LinkError) else LinkError(f"brak połączenia ({last})")

    # skróty
    def open_on(self, pid, url, title=""):
        return self.request(pid, "POST", "/v1/open", {"url": url, "title": title})

    def tabs_of(self, pid):
        return self.request(pid, "GET", "/v1/tabs", timeout=6).get("tabs", [])

    def clip_to(self, pid, text):
        return self.request(pid, "POST", "/v1/clip", {"text": text})

    def sync_with(self, pid, payload):
        return self.request(pid, "POST", "/v1/sync", payload, timeout=60)

    def remote(self, pid, cmd, value=None):
        return self.request(pid, "POST", "/v1/remote", {"cmd": cmd, "value": value}, timeout=5)

    def notify(self, pid, title, body="", kind=""):
        return self.request(pid, "POST", "/v1/notify", {"title": title, "body": body, "kind": kind}, timeout=5)

    def approve(self, pid, what, detail="", timeout=70):
        return bool(self.request(pid, "POST", "/v1/approve", {"what": what, "detail": detail}, timeout=timeout).get("ok"))

    def send_files(self, target, paths, progress=None, cancel=None):
        """target: id sparowanego urządzenia albo słownik z listy wykrytych (addr, port, fp). Zwraca liczbę wysłanych plików.
        progress(wysłane bajty, wszystkie bajty, nazwa pliku)."""
        if isinstance(target, str):
            p = self.state["peers"].get(target)
            if not p:
                raise LinkError("urządzenie nie jest sparowane")
            addrs, fp, token = self.addresses(target), p["fp"], p["token"]
        else:
            addrs, fp, token = [(target["addr"], target["port"])], target["fp"], None
        files = []
        for path in paths:
            pth = Path(path); h = hashlib.sha256()
            with open(pth, "rb") as f:
                for chunk in iter(lambda: f.read(CHUNK), b""):
                    h.update(chunk)
            files.append({"name": pth.name, "size": pth.stat().st_size, "sha256": h.hexdigest(), "type": _mime(pth.name)})
        total = sum(f["size"] for f in files); done = 0; last = None
        for addr, port in addrs:
            try:
                offer = self._call(addr, port, fp, "POST", "/v1/files", {"files": files}, token=token, timeout=75)
                break
            except (OSError, ssl.SSLError) as e:
                last = e
        else:
            raise LinkError(f"brak połączenia ({last})")
        sess, acc = offer.get("session"), offer.get("accept") or []
        sent = 0
        for i in acc:
            if cancel and cancel():
                raise LinkError("przerwano")
            f = files[int(i)]; pth = Path(paths[int(i)])
            c = self._conn(addr, port, fp, 30)
            try:
                c.putrequest("PUT", f"/v1/files/{sess}/{int(i)}")
                for k, v in self._headers(token, {"Content-Length": str(f["size"]), "Content-Type": "application/octet-stream"}).items():
                    c.putheader(k, v)
                c.endheaders()
                with open(pth, "rb") as fh:
                    for chunk in iter(lambda: fh.read(CHUNK), b""):
                        if cancel and cancel():
                            raise LinkError("przerwano")
                        c.send(chunk); done += len(chunk)
                        if progress:
                            progress(done, total, f["name"])
                r = c.getresponse(); body = r.read()
                if r.status >= 400:
                    try:
                        msg = json.loads(body.decode()).get("error")
                    except ValueError:
                        msg = None
                    raise LinkError(msg or f"błąd {r.status}")
                sent += 1
            finally:
                c.close()
        return sent

    # --- serwer: obsługa żądań ---
    def _auth(self, req):
        pid = req.headers.get("X-Luna-Id", ""); tok = req.headers.get("X-Luna-Token", "")
        p = self.state["peers"].get(pid)
        if p and tok and secrets.compare_digest(tok, p["token"]):
            return dict(p, id=pid, addr=req.client_address[0])
        return None

    def handle(self, req, method, path):
        """→ (kod, słownik) – wywoływane w wątku serwera."""
        peer = self._auth(req)
        if method == "GET" and path == "/v1/info":
            return 200, self.info()
        if method == "POST" and path == "/v1/pair":
            d = _read_json(req); d["_addr"] = req.client_address[0]
            try:
                return 200, self._accept_pair(d)
            except LinkError as e:
                return 403, {"error": str(e)}
        if method == "PUT" and path.startswith("/v1/files/"):
            return self._receive_file(req, path, peer)
        if method == "POST" and path == "/v1/files":
            return self._offer(req, peer)
        if peer is None:
            return 401, {"error": "urządzenie nie jest sparowane"}
        if peer.get("addr") and peer["addr"] != self.state["peers"][peer["id"]].get("addr"):
            with self.lock:
                self.state["peers"][peer["id"]]["addr"] = peer["addr"]; self.save()
        if method == "POST" and path == "/v1/unpair":
            with self.lock:
                self.state["peers"].pop(peer["id"], None); self.save()
            if peer["id"] in self.nearby:
                self.nearby[peer["id"]]["paired"] = False
            self.h.on_unpaired(peer)
            return 200, {}
        routes = {
            ("POST", "/v1/open"): ("open", lambda d: self.h.on_open(peer, str(d.get("url", "")), str(d.get("title", "")))),
            ("GET", "/v1/tabs"): ("tabs", lambda d: {"tabs": self.h.get_tabs(peer)}),
            ("POST", "/v1/clip"): ("clip", lambda d: self.h.on_clip(peer, str(d.get("text", ""))[:1_000_000])),
            ("POST", "/v1/sync"): ("sync", lambda d: self.h.on_sync(peer, d)),
            ("POST", "/v1/remote"): ("remote", lambda d: self.h.on_remote(peer, str(d.get("cmd", "")), d.get("value"))),
            ("POST", "/v1/notify"): ("notify", lambda d: self.h.on_notify(peer, str(d.get("title", ""))[:200],
                                                                          str(d.get("body", ""))[:1000], str(d.get("kind", "")))),
            ("POST", "/v1/approve"): ("approve", lambda d: {"ok": bool(self.h.on_approve(peer, str(d.get("what", "")),
                                                                                         str(d.get("detail", ""))))}),
        }
        r = routes.get((method, path))
        if not r:
            return 404, {"error": "nieznane żądanie"}
        feat, fn = r
        if not self.h.allowed(feat, peer):
            return 403, {"error": "ta funkcja jest wyłączona na tym urządzeniu"}
        d = _read_json(req) if method == "POST" else {}
        if feat == "open" and not re.match(r"https?://", str(d.get("url", "")), re.I):
            return 400, {"error": "można otwierać tylko adresy http(s)"}
        out = fn(d)
        return 200, out if isinstance(out, dict) else {}

    def _offer(self, req, peer):
        if not self.h.allowed("files_unpaired" if peer is None else "files", peer):
            return 403, {"error": "to urządzenie nie przyjmuje plików"}
        d = _read_json(req); files = d.get("files")
        if not isinstance(files, list) or not files or len(files) > 1000:
            return 400, {"error": "brak plików"}
        clean = []
        for f in files:
            try:
                clean.append({"name": safe_name(f.get("name")), "size": int(f.get("size", 0)),
                              "sha256": str(f.get("sha256", "")).lower(), "type": str(f.get("type", ""))[:100]})
            except (TypeError, ValueError, AttributeError):
                return 400, {"error": "niepoprawny opis pliku"}
        sender = peer or {"id": req.headers.get("X-Luna-Id", "")[:32], "addr": req.client_address[0], "paired": False,
                          "name": (self.nearby.get(req.headers.get("X-Luna-Id", "")) or {}).get("name", req.client_address[0])}
        acc = [i for i in (self.h.offer_files(sender, clean) or []) if 0 <= int(i) < len(clean)]
        if not acc:
            return 403, {"error": "odbiorca odrzucił pliki"}
        sid = secrets.token_hex(12)
        self.sessions[sid] = {"files": clean, "accept": set(acc), "sender": sender, "peer": peer and peer["id"],
                              "addr": req.client_address[0], "until": time.time() + 3600, "paths": []}
        return 200, {"session": sid, "accept": acc}

    def _receive_file(self, req, path, peer):
        m = re.fullmatch(r"/v1/files/([0-9a-f]{24})/(\d+)", path)
        s = self.sessions.get(m.group(1)) if m else None
        if not s or s["until"] < time.time() or req.client_address[0] != s["addr"] or \
                (s["peer"] and (peer is None or peer["id"] != s["peer"])):
            return 403, {"error": "nieznana albo wygasła sesja"}
        i = int(m.group(2))
        if i not in s["accept"]:
            return 403, {"error": "ten plik nie został przyjęty"}
        s["accept"].discard(i)
        f = s["files"][i]; size = int(req.headers.get("Content-Length") or -1)
        if size != f["size"]:
            return 400, {"error": "zły rozmiar pliku"}
        folder = Path(self.h.files_dir()); folder.mkdir(parents=True, exist_ok=True)
        dest = unique_path(folder, f["name"]); part = dest.with_name(dest.name + ".czesc")
        h = hashlib.sha256(); left = size
        try:
            with open(part, "wb") as out:
                while left > 0:
                    chunk = req.rfile.read(min(CHUNK, left))
                    if not chunk:
                        raise OSError("połączenie przerwane")
                    out.write(chunk); h.update(chunk); left -= len(chunk)
            if f["sha256"] and h.hexdigest() != f["sha256"]:
                raise ValueError("suma kontrolna się nie zgadza")
            dest = unique_path(folder, f["name"]); os.replace(part, dest)
        except (OSError, ValueError) as e:
            try:
                part.unlink()
            except OSError:
                pass
            return 400, {"error": f"plik odrzucony: {e}"}
        s["paths"].append(str(dest)); self.h.on_file(s["sender"], str(dest), f)
        if not s["accept"]:
            self.sessions.pop(m.group(1), None); self.h.on_files_done(s["sender"], s["paths"])
        return 200, {"saved": dest.name}


MIME = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".gif": "image/gif", ".webp": "image/webp",
        ".heic": "image/heic", ".mp4": "video/mp4", ".mov": "video/quicktime", ".mp3": "audio/mpeg", ".pdf": "application/pdf",
        ".zip": "application/zip", ".txt": "text/plain"}


def _mime(name):
    return MIME.get(Path(name).suffix.lower(), "application/octet-stream")


def _read_json(req):
    if getattr(req, "_json_cache", None) is not None:
        return req._json_cache
    n = int(req.headers.get("Content-Length") or 0)
    if n > MAX_JSON:
        raise ValueError("za duże żądanie")
    try:
        d = json.loads(req.rfile.read(n).decode("utf-8") or "{}") if n else {}
    except ValueError:
        d = {}
    req._json_cache = d if isinstance(d, dict) else {}
    return req._json_cache


def _make_req_handler(link):
    class R(BaseHTTPRequestHandler):
        server_version = "Luna"
        sys_version = ""
        protocol_version = "HTTP/1.1"
        timeout = 120

        def log_message(self, *a):
            pass

        def _do(self, method):
            self._json_cache = None
            try:
                code, body = link.handle(self, method, self.path.split("?", 1)[0])
            except ValueError as e:
                code, body = 400, {"error": str(e)}
            except Exception as e:   # błąd w Lunie nie może zabić serwera
                code, body = 500, {"error": f"błąd urządzenia: {type(e).__name__}"}
            raw = json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Connection", "close"); self.close_connection = True   # jedno żądanie na połączenie
            self.end_headers(); self.wfile.write(raw)

        def do_GET(self):
            self._do("GET")

        def do_POST(self):
            self._do("POST")

        def do_PUT(self):
            self._do("PUT")
    return R
