#!/bin/bash
# Generate self-signed TLS certificates for development/testing
# For production, use CA-signed certificates from your organization's PKI.

set -e

CERT_DIR="$(dirname "$0")/certs"
mkdir -p "$CERT_DIR"

echo "Generating self-signed TLS certificates for development..."

# Neo4j TLS certificate
openssl req -x509 -newkey rsa:4096 -keyout "$CERT_DIR/neo4j.key" -out "$CERT_DIR/neo4j.crt" \
    -days 365 -nodes -subj "/CN=neo4j/O=MuleCatch/C=IN"

# Nginx TLS certificate
openssl req -x509 -newkey rsa:4096 -keyout "$CERT_DIR/nginx.key" -out "$CERT_DIR/nginx.crt" \
    -days 365 -nodes -subj "/CN=mulecatch.local/O=MuleCatch/C=IN"

chmod 600 "$CERT_DIR"/*.key
chmod 644 "$CERT_DIR"/*.crt

echo "Certificates generated in $CERT_DIR/"
echo ""
echo "For production deployment:"
echo "  1. Obtain CA-signed certificates from your organization's PKI"
echo "  2. Replace the self-signed certs in $CERT_DIR/"
echo "  3. Set NEO4J_TLS_ENABLED=true in .env"
echo "  4. Uncomment the HTTPS server block in frontend/nginx.conf"
