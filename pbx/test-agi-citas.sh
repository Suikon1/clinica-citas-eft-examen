#!/usr/bin/env bash
# Prueba reproducible del AGI confirma_cita.py: simula a 3 pacientes
# respondiendo 1 (confirmar), 2 (cancelar) y 3 (reprogramar) y verifica
# que la BD de citas se actualiza y que se registra el log.
set -u
AST(){ sudo asterisk -rx "$1" 2>/dev/null; }

probar(){ # $1=ext  $2=digito
  AST "dialplan set global DIGITO $2" >/dev/null
  echo ">> Llamada automática de confirmación a paciente $1  (responde DTMF=$2)"
  AST "channel originate Local/$1@sim-paciente/n extension $1@citas" >/dev/null
  sleep 16
  AST "channel request hangup all" >/dev/null
  sleep 1
}

echo "===================== ESTADO INICIAL BD ====================="
sudo -u asterisk sqlite3 -header -column /var/lib/asterisk/agi-bin/citas.db \
  "SELECT paciente_ext,nombre,especialidad,fecha,hora,estado FROM citas;"

echo; echo "===================== EJECUCIÓN DE LLAMADAS ================="
probar 3002 1
probar 3003 2
probar 3001 3

echo; echo "===================== ESTADO FINAL BD ======================="
sudo -u asterisk sqlite3 -header -column /var/lib/asterisk/agi-bin/citas.db \
  "SELECT paciente_ext,nombre,especialidad,fecha,hora,estado,actualizado FROM citas;"

echo; echo "===================== LOG DE CONFIRMACIONES ================="
sudo tail -n 24 /var/log/asterisk/citas_confirmacion.log
