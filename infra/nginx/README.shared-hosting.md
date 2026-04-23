# Shared nginx on a host with multiple projects

This stack is designed so **local Docker Compose does not install or modify nginx** on the server.

When you deploy behind an existing nginx that serves other apps:

1. **Do not edit** other projects’ `server { }` blocks unless you are only adding a new `location` that cannot shadow their paths.
2. Prefer a **dedicated subdomain** (e.g. `audit.example.com`) with a **new** `server { }` file in `sites-available`, symlinked in `sites-enabled`, then `nginx -t` and `reload` — never replace the main config wholesale.
3. **Proxy only** to this project’s upstream (e.g. `127.0.0.1:8000` for API and `127.0.0.1:3000` for Next, or a single Next app proxying `/api` internally).
4. Keep **unique path prefixes** if you must share a domain: e.g. `location /yandex-audit/ { ... }` and configure Next `basePath` accordingly — avoid stealing `/`, `/api`, or paths used by other apps.
5. After changes: `sudo nginx -t` must pass before `sudo systemctl reload nginx` (reload, not restart, reduces blast radius).

Example **snippet** (adjust names, ports, TLS paths):

```nginx
# /etc/nginx/sites-available/yandex-direct-audit.conf
server {
    listen 443 ssl http2;
    server_name audit.your-domain.example;

    # ssl_certificate ...;
    # ssl_certificate_key ...;

    location /api/ {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location / {
        proxy_pass http://127.0.0.1:3000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

This file is documentation only; it is **not** mounted or applied by `docker-compose.yml`.
