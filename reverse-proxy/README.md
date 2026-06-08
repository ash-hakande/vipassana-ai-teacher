# Shared Docker Reverse Proxy

Use this when one VPS hosts multiple projects and one Docker nginx container owns public ports `80` and `443`.

## Routing

Default template routes:

| Domain placeholder | Upstream |
|---|---|
| `api.vipassana.example.com` | `host.docker.internal:9090` |
| `api.other.example.com` | `host.docker.internal:8080` |

Replace both placeholder domains in `nginx-initial.conf` and `nginx.conf`.

## Backend Projects

Run this project as backend-only:

```bash
cd ~/vipassana-ai-teacher
./dev.sh up
```

That exposes this backend on host port `9090`.

Run the other project backend on a different host port, for example `8080`.

## First Certificate Setup

Start with the HTTP-only config:

```bash
cd reverse-proxy
cp nginx-initial.conf nginx.conf
docker compose up -d nginx
```

Issue separate certificates:

```bash
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d api.vipassana.example.com
```

```bash
docker compose run --rm certbot certonly \
  --webroot \
  --webroot-path=/var/www/certbot \
  -d api.other.example.com
```

Restore the HTTPS `nginx.conf` template, with your real domains, then reload:

```bash
docker compose up -d nginx
docker compose exec nginx nginx -s reload
```

## Renewal

Run:

```bash
docker compose run --rm certbot renew
docker compose exec nginx nginx -s reload
```

Add that to cron on the VPS if desired.
