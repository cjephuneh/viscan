# Server blocks for the ViScan gateway. __DOMAIN__ is replaced at container
# start by 40-viscan-tls.sh (from the DOMAIN env var) and the result is
# written to /etc/nginx/conf.d/viscan.conf.

# ---------------------------------------------------------------------------
# 1. HTTP for the public domain: ACME challenge + redirect to HTTPS
# ---------------------------------------------------------------------------
server {
    listen 80;
    server_name __DOMAIN__ www.__DOMAIN__;

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
    }

    location / {
        return 301 https://__DOMAIN__$request_uri;
    }
}

# ---------------------------------------------------------------------------
# 2. HTTP for anything else (raw IP, localhost): serve the app directly.
#    Used by the server-side deployer's health check and while DNS is not
#    yet pointing at this host.
# ---------------------------------------------------------------------------
server {
    listen 80 default_server;
    server_name _;
    absolute_redirect off;   # keep host/port the client used in any redirect

    location ^~ /.well-known/acme-challenge/ {
        root /var/www/certbot;
        default_type text/plain;
    }

    include /etc/nginx/viscan-routes.conf;
}

# ---------------------------------------------------------------------------
# 3. HTTPS
# ---------------------------------------------------------------------------
server {
    listen 443 ssl default_server;
    http2 on;
    server_name __DOMAIN__ www.__DOMAIN__;
    absolute_redirect off;

    # Written by 40-viscan-tls.sh: Let's Encrypt cert when present,
    # otherwise a self-signed placeholder so nginx can always start.
    include /etc/nginx/tls-cert.conf;

    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
    ssl_session_tickets off;

    # 180 days HSTS; browsers only honour it over a valid certificate.
    add_header Strict-Transport-Security "max-age=15552000" always;

    if ($host = www.__DOMAIN__) {
        return 301 https://__DOMAIN__$request_uri;
    }

    include /etc/nginx/viscan-routes.conf;
}
