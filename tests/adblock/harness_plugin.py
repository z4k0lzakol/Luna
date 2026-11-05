"""Luna's ad blocker (adblock.AdBlock) as a plugin for the anti-adblock research harness.

The harness creates its QApplication BEFORE loading a plugin, which is too late to register our custom scheme
(surrogates would degrade to plain blocking). So run THIS file; it imports adblock first (scheme registered),
then starts the harness in plugin mode with itself as the plugin:

  python -I tests/adblock/harness_plugin.py --harness <dir>/harness.py --set suite --doh-proxy [other harness args]

Environment: LUNA_ADBLOCK_HOME = a home dir that already has ~/.luna_adblock (lists + build), e.g. from
tests/adblock/e2e_luna.py. Without it a temp home is used and the lists are downloaded and compiled first
(network, ~15 s). Never uses the real profile.
"""
import importlib.util
import os
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

import adblock  # noqa: E402  (registers the scheme while no QApplication exists)

_KEEP = []


class _Store:
    def __init__(self):
        self.settings = {}

    def feature(self, name):
        return True

    def save_soon(self):
        pass


def install(profile):
    from PyQt6.QtCore import QEventLoop, QTimer
    home = os.environ.get("LUNA_ADBLOCK_HOME") or tempfile.mkdtemp(prefix="luna_harness_")
    ab = adblock.AdBlock(_Store(), home=home)
    _KEEP.append(ab)
    if ab.net is None:   # no build yet: download + compile synchronously (harness waits)
        done = {}
        ab.update_list(lambda ok: done.__setitem__("ok", ok))
        end = time.time() + 240
        while "ok" not in done and time.time() < end:
            lp = QEventLoop()
            QTimer.singleShot(100, lp.quit)
            lp.exec()
    ab.install(profile)
    print(f"[luna-adblock] scheme_ok={adblock.SCHEME_OK} rules={ab.rules_total()} build={ab.build_dir}", flush=True)
    return ab


def _main():
    argv = sys.argv[1:]
    harness = None
    if "--harness" in argv:
        i = argv.index("--harness")
        harness = argv[i + 1]
        del argv[i:i + 2]
    if not harness or not os.path.isfile(harness):
        sys.exit("usage: harness_plugin.py --harness PATH/harness.py [harness args]")
    spec = importlib.util.spec_from_file_location("luna_harness", harness)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, os.path.dirname(os.path.abspath(harness)))
    spec.loader.exec_module(mod)
    sys.argv = [harness, "--mode", "plugin", "--plugin", os.path.abspath(__file__)] + argv
    mod.main()


if __name__ == "__main__":
    _main()
