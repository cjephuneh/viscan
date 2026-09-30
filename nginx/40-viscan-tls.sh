#!/bin/sh
# Runs before nginx starts (official image executes /docker-entrypoint.d/*).
#
#  1. Renders site.conf.tpl with $DOMAIN into conf.d/viscan.conf.
#  2. Makes sure a certificate exists so nginx can bind :443 immediately:
#     Let's Encrypt (written by the certbot sidecar) if present, otherwise a
#     self-signed placeholder.
#  3. Keeps watching the Let's Encrypt files; when they appear or change
#     (first issuance / renewal) it swaps the paths and reloads nginx.
set -eu

DOMAIN="${DOMAIN:-localhost}"
LE_DIR="/etc/letsencrypt/live/${DOMAIN}"
SS_DIR="/etc/nginx/certs"
CERT_CONF="/etc/nginx/tls-cert.conf"

mkdir -p "$SS_DIR" /var/www/certbot

sed "s/__DOMAIN__/${DOMAIN}/g" /etc/nginx/viscan-site.conf.tpl > /etc/nginx/conf.d/viscan.conf

if [ ! -s "$SS_DIR/fullchain.pem" ] || [ ! -s "$SS_DIR/privkey.pem" ]; then
    echo "[viscan-tls] generating self-signed placeholder certificate for ${DOMAIN}"
    openssl req -x509 -nodes -newkey rsa:2048 -days 3650 \
        -subj "/CN=${DOMAIN}" -addext "subjectAltName=DNS:${DOMAIN},DNS:www.${DOMAIN}" \
        -keyout "$SS_DIR/privkey.pem" -out "$SS_DIR/fullchain.pem" >/dev/null 2>&1
fi

write_cert_conf() {
    if [ -s "$LE_DIR/fullchain.pem" ] && [ -s "$LE_DIR/privkey.pem" ]; then
        dir="$LE_DIR"; kind="letsencrypt"
    else
        dir="$SS_DIR"; kind="self-signed"
    fi
    printf 'ssl_certificate     %s/fullchain.pem;\nssl_certificate_key %s/privkey.pem;\n' "$dir" "$dir" > "$CERT_CONF"
    echo "$kind"
}

kind="$(write_cert_conf)"
echo "[viscan-tls] ${DOMAIN}: using ${kind} certificate"

le_hash() { cat "$LE_DIR/fullchain.pem" 2>/dev/null | md5sum | cut -d' ' -f1; }

# Background watcher (survives the entrypoint's exec into nginx).
(
    last="$(le_hash)"
    while sleep 300; do
        cur="$(le_hash)"
        if [ "$cur" != "$last" ]; then
            last="$cur"
            kind="$(write_cert_conf)"
            echo "[viscan-tls] certificate for ${DOMAIN} changed -> ${kind}; reloading nginx"
            nginx -t >/dev/null 2>&1 && nginx -s reload || echo "[viscan-tls] reload failed"
        fi
    done
) &
