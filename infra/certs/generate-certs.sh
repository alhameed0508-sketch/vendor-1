#!/bin/bash
# Generate self-signed certificates for MuleCatch demo/dev
# For production, replace with proper CA-signed certificates

set -e

CERT_DIR="$(cd "$(dirname "$0")" && pwd)"
DAYS=365
SUBJECT="/C=IN/ST=TamilNadu/L=Chennai/O=MuleCatch/CN=localhost"

echo "Generating self-signed certificates in $CERT_DIR..."

openssl req -x509 -nodes \
    -days "$DAYS" \
    -newkey rsa:2048 \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.crt" \
    -subj "$SUBJECT" \
    -addext "subjectAltName=DNS:localhost,DNS:mulecatch,IP:127.0.0.1"

echo "Certificates generated:"
echo "  Key:  $CERT_DIR/server.key"
echo "  Cert: $CERT_DIR/server.crt"
echo ""
echo "Valid for $DAYS days."
echo "WARNING: These are self-signed certs for demo/dev only."
