"""Stamp one cache-busting version onto every local script, stylesheet and data URL in web/.

Cloudflare caches .js/.css/.json at the edge for hours, so a deploy is not visible until the URLs change.
ES modules are identified by their full URL, so every import of a module must carry the SAME version,
otherwise the browser loads two copies and shared state splits. This rewrites all of them together.
Run before each deploy:  python3 scripts/stamp_version.py            (version = UTC timestamp)
                         python3 scripts/stamp_version.py 20260923a  (explicit version)"""
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

WEB = Path(__file__).resolve().parent.parent / "web"
ver = sys.argv[1] if len(sys.argv) > 1 else datetime.now(timezone.utc).strftime("%Y%m%d%H%M")

# ./x.js, ../x.js, app.js, app.css in import/src/href, with or without an existing ?v=
LOCAL_REF = re.compile(r"""((?:from\s+|import\(\s*|src=|href=)["'])((?:\./|\.\./)?[\w./-]+\.(?:js|css))(?:\?v=[\w.-]+)?(["'])""")
DATA_CONST = re.compile(r"export const DATA_VERSION = '[^']*';")

changed = 0
for f in [WEB / "index.html", WEB / "app.js", *sorted((WEB / "js").rglob("*.js"))]:
    s = f.read_text()
    t = LOCAL_REF.sub(lambda m: f"{m.group(1)}{m.group(2)}?v={ver}{m.group(3)}", s)
    t = DATA_CONST.sub(f"export const DATA_VERSION = '{ver}';", t)
    if t != s:
        f.write_text(t)
        changed += 1
print(f"stamped v={ver} in {changed} files")
