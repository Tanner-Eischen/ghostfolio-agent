#!/bin/sh
set -e

# Default values for local development
: "${BACKEND_URL:=http://localhost:8000}"
: "${BACKEND_HOST:=localhost:8000}"

# Extract host from BACKEND_URL if BACKEND_HOST not explicitly set
if [ "$BACKEND_HOST" = "localhost:8000" ] && echo "$BACKEND_URL" | grep -q "^https\?://"; then
    # Extract host (without protocol and path)
    BACKEND_HOST=$(echo "$BACKEND_URL" | sed -E 's|^https?://([^/]+).*|\1|')
fi

echo "Configuring nginx with BACKEND_URL=$BACKEND_URL and BACKEND_HOST=$BACKEND_HOST"

# Substitute environment variables in nginx config
# Create a temporary file with substitutions
envsubst '${BACKEND_URL} ${BACKEND_HOST}' < /etc/nginx/conf.d/default.conf > /tmp/nginx.conf
mv /tmp/nginx.conf /etc/nginx/conf.d/default.conf

echo "nginx configuration complete. Starting server..."

# Start nginx
exec nginx -g 'daemon off;'
