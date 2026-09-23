#!/bin/sh
# Installs the Demand Evidence assistant: systemd unit, nginx rate-limit zone, /demand-evidence/api/ route.
# Run with sudo on jarvis. Backs up the nginx apps config and restores it if the config test fails.
set -e
cd /home/mohith/demand-evidence/deploy
cp /etc/nginx/sites-available/apps /etc/nginx/sites-available/apps.bak-demand-evidence
cp demand-evidence-ratelimit.conf /etc/nginx/conf.d/demand-evidence-ratelimit.conf
cp apps.nginx /etc/nginx/sites-available/apps
if ! nginx -t; then
  echo "nginx config test failed: restoring the previous config"
  cp /etc/nginx/sites-available/apps.bak-demand-evidence /etc/nginx/sites-available/apps
  rm -f /etc/nginx/conf.d/demand-evidence-ratelimit.conf
  nginx -t && exit 1
fi
cp demand-evidence.service /etc/systemd/system/demand-evidence.service
systemctl daemon-reload
systemctl enable --now demand-evidence
systemctl reload nginx
sleep 3
systemctl is-active demand-evidence
curl -s http://127.0.0.1:5021/api/health; echo
