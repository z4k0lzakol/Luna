"""Public Suffix List (publicsuffix.org, MPL-2.0; downloaded at runtime, never committed).

parse(text) -> dict  {suffix(punycode): flags}  flags: 1 = rule, 2 = wildcard "*.suffix", 4 = exception "!suffix"
PSL(data|None): registrable(host), public_suffix(host), entity_keys(host)
Without data a heuristic is used (Luna's base_domain: 2 labels, 3 when the 2nd-level label is a common SLD).
"""
import marshal

RULE, WILD, EXC = 1, 2, 4
_SLD = {"co", "com", "org", "net", "gov", "edu", "ac", "gob"}


def _puny(s):
    s = s.strip().lower().rstrip(".")
    if s.isascii():
        return s
    try:
        return s.encode("idna").decode("ascii")
    except Exception:
        try:
            return ".".join(p if p.isascii() else "xn--" + p.encode("punycode").decode("ascii")
                            for p in s.split("."))
        except Exception:
            return None


def parse(text):
    """PSL .dat text -> marshal-able dict (both ICANN and PRIVATE sections)."""
    d = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("//"):
            continue
        rule = line.split()[0]
        flag = RULE
        if rule.startswith("!"):
            flag, rule = EXC, rule[1:]
        elif rule.startswith("*."):
            flag, rule = WILD, rule[2:]
        elif "*" in rule:
            continue                       # inner wildcards are not used by the PSL
        rule = _puny(rule)
        if rule:
            d[rule] = d.get(rule, 0) | flag
    return d


def _is_ip(host):
    if ":" in host or host.startswith("["):
        return True
    p = host.split(".")
    return len(p) == 4 and all(x.isdigit() for x in p)


class PSL:
    def __init__(self, data=None):
        self.data = data or None
        self._cache = {}

    @classmethod
    def load(cls, path):
        """path: psl.bin (marshal of parse()) or public_suffix_list.dat; missing/broken -> heuristic."""
        try:
            with open(path, "rb") as f:
                raw = f.read()
            try:
                d = marshal.loads(raw)
                if isinstance(d, dict):
                    return cls(d)
            except Exception:
                pass
            return cls(parse(raw.decode("utf-8", "replace")))
        except Exception:
            return cls(None)

    def public_suffix(self, host):
        host = (host or "").lower().rstrip(".")
        if not host or _is_ip(host):
            return host
        labels = host.split(".")
        n = len(labels)
        d = self.data
        if d is None:
            if n >= 3 and labels[-2] in _SLD:
                return ".".join(labels[-2:])
            return labels[-1]
        get = d.get
        for i in range(n):
            s = ".".join(labels[i:])
            f = get(s, 0)
            if f & EXC:
                return ".".join(labels[i + 1:])
            if f & RULE:
                return s
            if i + 1 < n and get(".".join(labels[i + 1:]), 0) & WILD:
                return s
        return labels[-1]

    def registrable(self, host):
        """'a.b.example.co.uk' -> 'example.co.uk'. A bare public suffix or an IP returns itself."""
        host = (host or "").lower().rstrip(".")
        r = self._cache.get(host)
        if r is not None:
            return r
        ps = self.public_suffix(host)
        if not ps or ps == host or not host.endswith("." + ps):
            r = host
        else:
            r = host[:-(len(ps) + 1)].rsplit(".", 1)[-1] + "." + ps
        if len(self._cache) > 8192:
            self._cache.clear()
        self._cache[host] = r
        return r

    def entity_keys(self, host):
        """'b.example.co.uk' -> ['example.*', 'b.example.*'] (entity filter keys, most general first)."""
        host = (host or "").lower().rstrip(".")
        if not host or _is_ip(host):
            return []
        ps = self.public_suffix(host)
        if not ps or ps == host or not host.endswith("." + ps):
            return []
        labels = host[:-(len(ps) + 1)].split(".")
        out = []
        for i in range(len(labels) - 1, -1, -1):
            out.append(".".join(labels[i:]) + ".*")
        return out
