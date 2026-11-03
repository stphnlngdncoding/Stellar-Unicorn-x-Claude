#!/bin/bash
# Updates your Unicorn cloud Worker (keeping its secrets) and prints the
# address of the Unicorn Remote phone app. Run from anywhere:
#   bash cloud/deploy-app.sh
# Changed the Remote? Run  python3 remote/build_app.py  first.
set -e
cd "$(dirname "$0")"

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js isn't installed. Get the LTS version from https://nodejs.org, then run this again."
  exit 1
fi

echo "==> Installing tools"
npm install --no-audit --no-fund --silent

echo "==> Signing in to Cloudflare (a browser window may open)"
npx wrangler whoami 2>/dev/null | grep -qi "associated with the email" || npx wrangler login

echo "==> Deploying"
npx wrangler deploy

echo
echo "================================================================"
if [ -f connector-url.txt ]; then
  APP=$(sed -e 's#/mcp/#/app/#' -e 's#/*$#/#' connector-url.txt)
  echo " Unicorn Remote app:"
  echo "   $APP"
else
  echo " Your app address is your connector URL with /mcp/ changed to /app/"
  echo " and a / on the end:  https://....workers.dev/app/<secret>/"
fi
echo
echo " On your iPhone: open it in Safari, tap Share, then Add to Home Screen."
echo " Keep the address private: like the connector URL, it controls your board."
echo "================================================================"
