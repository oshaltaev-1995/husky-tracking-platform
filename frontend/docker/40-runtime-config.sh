#!/bin/sh
set -eu

: "${PUBLIC_BASE_URL:?PUBLIC_BASE_URL is required}"
envsubst '${PUBLIC_BASE_URL}' \
  < /etc/nginx/templates/runtime-config.template.js \
  > /usr/share/nginx/html/runtime-config.js
