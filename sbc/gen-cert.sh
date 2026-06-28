#!/usr/bin/env bash
# Genera el certificado TLS del SBC (Kamailio) para la señalización SIP segura
# de la Clínica Regional "Salud Integral".  Self-signed, válido 825 días.
# Uso:  sudo bash gen-cert.sh <IP_PUBLICA_SBC> <IP_PRIVADA_SBC>
set -e
PUB="${1:?IP publica requerida}"
PRIV="${2:-172.31.57.212}"
DIR=/etc/kamailio/tls
sudo mkdir -p "$DIR"

sudo openssl req -x509 -newkey rsa:2048 -nodes \
  -keyout "$DIR/server.key" -out "$DIR/server.crt" -days 825 \
  -subj "/C=CL/ST=Region Metropolitana/L=Santiago/O=Clinica Regional Salud Integral/OU=Telecomunicaciones/CN=${PUB}" \
  -addext "subjectAltName=IP:${PUB},IP:${PRIV}" \
  -addext "keyUsage=digitalSignature,keyEncipherment" \
  -addext "extendedKeyUsage=serverAuth,clientAuth"

sudo chown kamailio:kamailio "$DIR/server.key" "$DIR/server.crt"
sudo chmod 640 "$DIR/server.key"
echo "== Certificado generado =="
sudo openssl x509 -in "$DIR/server.crt" -noout -subject -issuer -dates -ext subjectAltName
