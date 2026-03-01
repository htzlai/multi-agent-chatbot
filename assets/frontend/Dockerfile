FROM node:20-alpine AS base
RUN corepack enable && corepack prepare pnpm@latest --activate
WORKDIR /app

# --- deps ---
FROM base AS deps
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

# --- build ---
FROM base AS build
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build:prod

# --- production (Nginx serving dist/) ---
FROM nginx:alpine AS production
COPY --from=build /app/dist /usr/share/nginx/html
COPY <<'EOF' /etc/nginx/conf.d/default.conf
server {
    listen 80;
    server_name _;
    root /usr/share/nginx/html;
    index index.html;

    # SPA fallback — all non-file routes to index.html
    location / {
        try_files $uri $uri/ /index.html;
    }

    # Cache static assets
    location ~* \.(js|css|png|jpg|jpeg|gif|ico|svg|woff2?)$ {
        expires 1y;
        add_header Cache-Control "public, immutable";
    }

    # Security headers
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header Referrer-Policy "strict-origin-when-cross-origin" always;
}
EOF
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]

# --- dev (for docker-compose volume mount) ---
FROM base AS dev
COPY package.json pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
EXPOSE 3000
CMD ["pnpm", "dev", "--host", "0.0.0.0"]
