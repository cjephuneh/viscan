FROM nginx:alpine

# openssl: self-signed placeholder cert until Let's Encrypt has issued one.
RUN apk add --no-cache openssl && rm -f /etc/nginx/conf.d/default.conf

COPY nginx.conf        /etc/nginx/nginx.conf
COPY routes.conf       /etc/nginx/viscan-routes.conf
COPY site.conf.tpl     /etc/nginx/viscan-site.conf.tpl
COPY 40-viscan-tls.sh  /docker-entrypoint.d/40-viscan-tls.sh
RUN chmod +x /docker-entrypoint.d/40-viscan-tls.sh

# Public domain served over HTTPS (override via the DOMAIN env var).
ENV DOMAIN=viscan.site

EXPOSE 80 443

HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD wget -qO- http://127.0.0.1/health || exit 1
