#!/usr/bin/env bash
# Registra 3 softphones (baresip) contra la PBX local y deja todo listo
# para probar registro y llamadas internas. Audio dummy (aubridge) porque
# la VM no tiene tarjeta de sonido. answermode=auto -> auto-contesta.
set -e
BSDIR=/home/ubuntu/.baresip
pkill -x baresip 2>/dev/null || true
sleep 1
mkdir -p "$BSDIR"

# --- cuentas: 3001, 3002, 3003 ---
cat > "$BSDIR/accounts" <<'EOF'
<sip:3001@127.0.0.1>;auth_user=3001;auth_pass=Clinica.3001;answermode=auto;regint=120;audio_codecs=PCMU/8000,PCMA/8000
<sip:3002@127.0.0.1>;auth_user=3002;auth_pass=Clinica.3002;answermode=auto;regint=120;audio_codecs=PCMU/8000,PCMA/8000
<sip:3003@127.0.0.1>;auth_user=3003;auth_pass=Clinica.3003;answermode=auto;regint=120;audio_codecs=PCMU/8000,PCMA/8000
EOF

# --- config: puerto SIP propio 5062, audio aubridge (loopback, sin tarjeta) ---
cfg="$BSDIR/config"
# desactivar drivers de audio de hardware y stdio (corre headless)
sed -i -E 's/^[[:space:]]*module[[:space:]]+(alsa|pulse|stdio)\.so/#&/' "$cfg"
# quitar cualquier directiva de audio previa
sed -i '/^audio_player/d; /^audio_source/d; /^audio_alert/d' "$cfg"
# limpiar bloque previo nuestro
sed -i '/# --- EFT overrides ---/,$d' "$cfg"
cat >> "$cfg" <<'EOF'
# --- EFT overrides ---
sip_listen              0.0.0.0:5062
module                  aubridge.so
audio_source            aubridge,bridge
audio_player            aubridge,bridge
audio_alert             aubridge,bridge
EOF

nohup baresip -f "$BSDIR" </dev/null >/home/ubuntu/baresip.log 2>&1 &
echo "baresip lanzado (PID $!). Esperando registro..."
sleep 6
echo "===== baresip.log (cola) ====="
tail -n 15 /home/ubuntu/baresip.log
