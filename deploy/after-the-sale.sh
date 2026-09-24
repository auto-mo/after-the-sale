#!/usr/bin/env bash
# One-time switch from /demand-evidence/ to /after-the-sale/ on Jarvis. Run by the owner:
#   ssh -t jarvis 'sudo bash ~/demand-evidence/deploy/after-the-sale.sh'
# Adds the /after-the-sale/api/ proxy (same limits as before), redirects every /demand-evidence/ URL to the new path,
# checks the config, reloads nginx and restarts the assistant so it loads the new code and tables.
# The previous config is kept as apps.bak-<timestamp> next to the original.
set -euo pipefail
CONF=/etc/nginx/sites-available/apps
cp "$CONF" "$CONF.bak-$(date +%Y%m%d%H%M%S)"

python3 - "$CONF" <<'PY'
import re, sys
p = sys.argv[1]
s = open(p).read()
if "/after-the-sale/api/" in s:
    print("already switched; nothing to change")
    sys.exit(0)
old = re.search(r"    # Demand Evidence assistant API.*?\n    location /demand-evidence/api/ \{.*?\n    \}\n", s, re.S)
if not old:
    sys.exit("could not find the /demand-evidence/api/ block; no change made")
new = old.group(0).replace("# Demand Evidence assistant API (gunicorn :5021). The page itself is static at /demand-evidence/.",
                           "# After the Sale assistant API (gunicorn :5021). The page itself is static at /after-the-sale/.")
new = new.replace("location /demand-evidence/api/", "location /after-the-sale/api/")
new += ("    # Old name: every /demand-evidence/ URL moves to /after-the-sale/, keeping the rest of the path.\n"
        "    location ^~ /demand-evidence/ { rewrite ^/demand-evidence/(.*)$ /after-the-sale/$1 permanent; }\n"
        "    location = /demand-evidence { return 301 /after-the-sale/; }\n"
        "    location = /after-the-sale { return 301 /after-the-sale/; }\n")
s = s.replace(old.group(0), new)
open(p, "w").write(s)
print("nginx config updated")
PY

nginx -t
systemctl reload nginx
systemctl restart demand-evidence
sleep 2
systemctl is-active demand-evidence
curl -s http://127.0.0.1:5021/api/health; echo
