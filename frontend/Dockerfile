# Frontend Dockerfile for Railway when Root Directory = "frontend"
# Build context is frontend/ so paths are relative to this directory.

FROM node:20-alpine AS builder
WORKDIR /app

COPY package*.json ./
RUN npm ci
COPY . .
ARG VITE_API_URL
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

FROM nginx:alpine AS production
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh
COPY --from=builder /app/dist /usr/share/nginx/html

# Backend URL environment variables (set in Railway or at runtime)
# BACKEND_URL: Full URL including protocol (e.g., https://your-backend.up.railway.app)
# BACKEND_HOST: Host header for proxy (extracted from BACKEND_URL if not set)
ENV BACKEND_URL=http://localhost:8000
ENV BACKEND_HOST=localhost:8000
ENV PORT=8080

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -q -O /dev/null http://localhost:8080/ || exit 1

ENTRYPOINT ["/docker-entrypoint.sh"]
