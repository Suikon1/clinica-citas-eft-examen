#!/usr/bin/env bash
# Entrypoint del contenedor PBX: inicializa la BD de citas + audios TTS
# y arranca la API de citas y Asterisk en primer plano.
set -e

# Inicializar BD de citas y generar audios TTS (idempotente)
su asterisk -s /bin/bash -c "python3 /usr/share/asterisk/agi-bin/seed_citas.py" || \
    echo "[entrypoint] aviso: seed parcial (¿sin red para gTTS? usará espeak)"

# API REST de citas en segundo plano
su asterisk -s /bin/bash -c "python3 /usr/local/bin/citas_api.py 8080" &

echo "[entrypoint] Arrancando Asterisk (PBX Clínica Salud Integral)..."
exec asterisk -f -U asterisk -G asterisk
