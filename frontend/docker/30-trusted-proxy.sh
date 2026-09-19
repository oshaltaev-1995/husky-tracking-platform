#!/bin/sh
set -eu

trusted_cidr="${TRUSTED_PROXY_CIDR:-127.0.0.1/32}"
if ! printf '%s\n' "$trusted_cidr" | grep -Eq '^([0-9]{1,3}\.){3}[0-9]{1,3}/(2[4-9]|3[0-2])$'; then
    echo 'TRUSTED_PROXY_CIDR must be one narrow reviewed IPv4 CIDR (/24 to /32)' >&2
    exit 1
fi

# Never substitute the Nginx configuration wholesale: its own $variables must
# remain intact. Nginx validates the address and fails startup if it is invalid.
printf 'set_real_ip_from %s;\n' "$trusted_cidr" > /etc/nginx/trusted-proxy.conf
nginx -t -q
