# Stage 1: Build React app
FROM node:20-alpine AS builder
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps
COPY . .
RUN npm run build

# Stage 2: Serve with nginx (non-root)
FROM nginx:alpine AS runner

# Remove default nginx config
RUN rm -rf /etc/nginx/conf.d/default.conf

# Create non-root user and fix permissions for nginx
RUN addgroup -g 1001 -S appgroup && adduser -S appuser -u 1001 -G appgroup \
    && chown -R appuser:appgroup /var/cache/nginx /var/log/nginx \
    && touch /var/run/nginx.pid && chown appuser:appgroup /var/run/nginx.pid

# Copy built assets and config
COPY --from=builder --chown=appuser:appgroup /app/build /usr/share/nginx/html
COPY --chown=appuser:appgroup nginx.conf /etc/nginx/conf.d/default.conf

USER appuser

EXPOSE 80

HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://127.0.0.1:80/health || exit 1

CMD ["nginx", "-g", "daemon off;"]
