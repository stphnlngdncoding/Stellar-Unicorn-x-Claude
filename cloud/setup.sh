#!/bin/bash
# Deploys the Unicorn cloud service to your Cloudflare account, generates the
# two secrets, and writes board/_cloud.json for you.
# Run from the cloud/ folder:  bash setup.sh
set -e
cd "$(dirname "$0")"

if ! command -v npm >/dev/null 2>&1; then
  echo "Node.js isn't installed. Get the LTS version from https://nodejs.org, then run this again."
  exit 1
fi

BOARD_TOKEN=$(node -e "console.log(require('crypto').randomBytes(24).toString('base64url'))")
MCP_SECRET=$(node -e "console.log(require('crypto').randomBytes(16).toString('hex'))")

echo "==> Installing tools"
npm install --no-audit --no-fund --silent

echo "==> Signing in to Cloudflare (a browser window may open)"
npx wrangler whoami 2>/dev/null | grep -qi "associated with the email" || npx wrangler login

echo "==> Deploying"
npx wrangler deploy 2>&1 | tee deploy.log

echo "==> Storing secrets"
printf '%s' "$BOARD_TOKEN" | npx wrangler secret put BOARD_TOKEN >/dev/null
printf '%s' "$MCP_SECRET"  | npx wrangler secret put MCP_SECRET >/dev/null

URL=$(grep -Eo 'https://[A-Za-z0-9.-]+\.workers\.dev' deploy.log | head -1)
if [ -z "$URL" ]; then
  echo "Deployed, but couldn't find the workers.dev address in the output above."
  read -r -p "Paste your https://...workers.dev address: " URL
fi

printf '{"url": "%s", "token": "%s"}\n' "$URL" "$BOARD_TOKEN" > ../board/_cloud.json
echo "$URL/mcp/$MCP_SECRET" > connector-url.txt

echo
echo "================================================================"
echo " Done!"
echo
echo " Connector URL (add it to Claude as a custom connector):"
echo "   $URL/mcp/$MCP_SECRET"
echo
echo " Board settings written to board/_cloud.json; copy that file to the board."
echo "================================================================"
echo "Both are git-ignored. Keep the connector URL private: anyone with it"
echo "can control your board."
