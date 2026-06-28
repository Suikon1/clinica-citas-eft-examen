# Solución PBX dockerizada — Clínica Regional "Salud Integral" (EFT CUY5132)
# Empaqueta Asterisk 18 (PJSIP) + AGI de confirmación de citas + BD SQLite
# + TTS (gTTS/espeak) + API REST de citas.  Base Ubuntu 22.04 (igual que la VM).
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
        asterisk asterisk-modules asterisk-config \
        python3 python3-pip ffmpeg espeak-ng sqlite3 sox baresip ca-certificates \
    && pip3 install --no-cache-dir gTTS \
    && apt-get clean && rm -rf /var/lib/apt/lists/*

# --- Configuración de Asterisk (PJSIP + dialplan) ---
COPY pbx/etc-asterisk/pjsip.conf       /etc/asterisk/pjsip.conf
COPY pbx/etc-asterisk/extensions.conf  /etc/asterisk/extensions.conf

# --- AGI, BD y TTS ---
COPY pbx/agi-bin/confirma_cita.py      /usr/share/asterisk/agi-bin/confirma_cita.py
COPY pbx/db/seed_citas.py              /usr/share/asterisk/agi-bin/seed_citas.py
COPY pbx/api/citas_api.py              /usr/local/bin/citas_api.py

# Desactivar chan_sip para que PJSIP use el 5060; permitir AGI ejecutable
RUN sed -i '/\[modules\]/a noload => chan_sip.so' /etc/asterisk/modules.conf \
    && chmod +x /usr/share/asterisk/agi-bin/confirma_cita.py \
    && mkdir -p /var/lib/asterisk/agi-bin /var/lib/asterisk/sounds/citas \
    && chown -R asterisk:asterisk /var/lib/asterisk /usr/share/asterisk/agi-bin

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# SIP (UDP/TCP), SIP-TLS, RTP y API de citas
EXPOSE 5060/udp 5060/tcp 5061/tcp 8080/tcp 10000-10100/udp

ENTRYPOINT ["/entrypoint.sh"]
