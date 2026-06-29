# Comandos de validación — EFT CUY5132 (Sistema de Confirmación de Citas)

Guía para **verificar/demostrar** que cada parte del sistema funciona. Cada bloque indica
**DÓNDE** se ejecuta, el **COMANDO** y **QUÉ SE ESPERA** ver.

---

## 0. Datos de conexión

> ⚠️ Las IP **públicas** de la PBX y el SBC **cambian al reiniciar el lab**. n8n conserva su IP fija.
> Actualízalas aquí si reinicias. Para obtenerlas: `aws ec2 describe-instances --region us-east-1 --query 'Reservations[].Instances[].{N:Tags[?Key==\`Name\`]|[0].Value,IP:PublicIpAddress}' --output table`

| Recurso | Valor actual |
|---|---|
| PBX (Asterisk) | `100.26.56.46` |
| SBC (Kamailio) | `54.210.44.135` |
| n8n | `https://18-213-161-67.nip.io` |
| Clave SSH | `~/Documentos/Duoc/ServUni/Examen/lab.pem` |
| Webhook n8n | `https://18-213-161-67.nip.io/webhook/cita-confirmacion` |

Atajos (pégalos en la terminal **local** para reutilizarlos):
```bash
cd ~/Documentos/Duoc/ServUni/Examen
PEM=./lab.pem ; PBX=100.26.56.46 ; SBC=54.210.44.135 ; N8N=https://18-213-161-67.nip.io
sshpbx(){ ssh -i $PEM -o StrictHostKeyChecking=no ubuntu@$PBX "$@"; }
sshsbc(){ ssh -i $PEM -o StrictHostKeyChecking=no ubuntu@$SBC "$@"; }
```

---

## Indicador 1 — Extensiones SIP (PJSIP) · 15%

**DÓNDE:** terminal local (usa `sshpbx`).
```bash
# Las 3 extensiones registradas (estado Avail):
sshpbx 'sudo asterisk -rx "pjsip show contacts"'
# Endpoints y transportes:
sshpbx 'sudo asterisk -rx "pjsip show endpoints"'
sshpbx 'sudo asterisk -rx "pjsip show transports"'
# Llamada interna 3002 -> 3003:
sshpbx 'sudo asterisk -rx "channel originate PJSIP/3002 extension 3003@internal"; sleep 3; sudo asterisk -rx "core show channels"'
```
**SE ESPERA:** 3 contactos `3001/3002/3003 ... Avail`; 2 transportes (udp/tcp 5060); durante la
llamada, 2 canales en estado `Up`. CDR `ANSWERED` en `/var/log/asterisk/cdr-csv/Master.csv`.

> Si las extensiones NO aparecen registradas (tras reiniciar el lab), relanza los softphones:
> `sshpbx 'pkill -x baresip; nohup baresip -f /home/ubuntu/.baresip </dev/null >/home/ubuntu/baresip.log 2>&1 & sleep 5; sudo asterisk -rx "pjsip show contacts"'`

---

## Indicador 2 — Script AGI: DTMF + BD + log · 20%

**DÓNDE:** terminal local (usa `sshpbx`).
```bash
# Estado inicial de las citas:
sshpbx 'sudo -u asterisk sqlite3 -column /var/lib/asterisk/agi-bin/citas.db "SELECT paciente_ext,nombre,especialidad,fecha,hora,estado FROM citas;"'

# Llamada de confirmación: el paciente 3002 presiona 1 (confirmar)
sshpbx 'sudo asterisk -rx "dialplan set global DIGITO 1"; sudo asterisk -rx "channel originate Local/3002@sim-paciente/n extension 3002@citas"'
sleep 14
# Resultado en la BD + log:
sshpbx 'sudo -u asterisk sqlite3 -column /var/lib/asterisk/agi-bin/citas.db "SELECT paciente_ext,estado,actualizado FROM citas;"'
sshpbx 'sudo cat /var/log/asterisk/citas_confirmacion.log'
sshpbx 'sudo column -s, -t /var/lib/asterisk/agi-bin/confirmaciones.csv'
```
Para probar **2 (cancelar)** y **3 (reprogramar)**: cambia `DIGITO 1` por `DIGITO 2` / `DIGITO 3`
y el `3002` por `3003` / `3001`.

**SE ESPERA:** el estado del paciente pasa a `CONFIRMADA` (1) / `CANCELADA` (2) / `REPROGRAMAR` (3);
el log muestra `Inicio confirmación`, `presionó N -> ESTADO`, `Fin confirmación`; el CSV registra la fila.

Reset a estado inicial:
```bash
sshpbx 'sudo -u asterisk sqlite3 /var/lib/asterisk/agi-bin/citas.db "UPDATE citas SET estado=\"PENDIENTE\", actualizado=NULL;"'
```

---

## Indicador 3 — SBC + Security Groups (aislamiento) · 10%

**DÓNDE:** terminal local (las pruebas de alcance salen de tu equipo).
```bash
# La PBX NO es accesible desde Internet (debe dar timeout):
timeout 6 bash -c "echo > /dev/tcp/$PBX/5060" && echo ABIERTO || echo "BLOQUEADO (correcto)"
# El SBC SÍ es accesible (debe abrir):
timeout 6 bash -c "echo > /dev/tcp/$SBC/5060" && echo "ABIERTO (correcto)" || echo BLOQUEADO
# Reglas de los Security Groups:
aws ec2 describe-security-groups --region us-east-1 --group-ids sg-0e3079747a3f20c73 \
  --query 'SecurityGroups[0].IpPermissions[].{Proto:IpProtocol,Port:FromPort,CIDR:IpRanges[0].CidrIp,SG:UserIdGroupPairs[0].GroupId}' --output table   # SG-PBX
aws ec2 describe-security-groups --region us-east-1 --group-ids sg-0e696a206eaefc206 \
  --query 'SecurityGroups[0].IpPermissions[].{Proto:IpProtocol,Port:FromPort,CIDR:IpRanges[0].CidrIp}' --output table   # SG-SBC
```
**SE ESPERA:** PBX:5060 → BLOQUEADO; SBC:5060 → ABIERTO. SG-PBX expone SIP/RTP solo con `SG=sg-0e696...`
(el del SBC); SG-SBC expone 5060/5061/RTP a `0.0.0.0/0`.

---

## Indicador 4 — Enrutamiento del SBC · 10%

**DÓNDE:** terminal local (usa `sshsbc`).
```bash
# Lógica de enrutamiento (t_relay hacia la PBX + record_route):
sshsbc "sudo sed -n '40,90p' /etc/kamailio/kamailio.cfg"
# Kamailio activo y escuchando:
sshsbc 'sudo systemctl is-active kamailio; sudo ss -tulnp | grep -E ":(5060|5061)"'
```
**SE ESPERA:** `request_route` con `record_route()`, `$du="sip:172.31.57.229:5060"` y `t_relay()`;
Kamailio `active` escuchando UDP/TCP 5060 y TLS 5061.

---

## Indicador 5 — TLS de señalización · 15%

**DÓNDE:** terminal local.
```bash
# Certificado de la clínica en el puerto público + TLS 1.3:
echo | openssl s_client -connect $SBC:5061 2>/dev/null | openssl x509 -noout -subject -issuer -dates
echo | openssl s_client -connect $SBC:5061 2>/dev/null | grep -E "Protocol|Cipher is"
```
**SE ESPERA:** `subject ... O = Clinica Regional Salud Integral ... CN = <IP SBC>`; `TLSv1.3`,
`Cipher ... AES_256_GCM`. (La comparación claro-vs-cifrado está en la evidencia `ev-ind5-02`.)

---

## Indicador 6 — Flujo n8n (webhook + BD) · 15%

**DÓNDE:** terminal local + navegador.
```bash
# Disparar el flujo (consulta BD -> IA -> TTS -> Slack -> respuesta):
curl -sk -X POST $N8N/webhook/cita-confirmacion -H "Content-Type: application/json" \
  -d '{"ext":"3002"}' | python3 -m json.tool
```
**SE ESPERA:** JSON con `ok:true`, el objeto `cita` (datos reales de la BD), `recordatorio` (texto IA)
y `tts` (motor + bytes). En el navegador (`$N8N`, workflow «EFT - Confirmación de Citas»), pestaña
**Executions** → todos los nodos en verde; y el mensaje publicado en el canal de **Slack**.

---

## Indicador 7 — TTS dinámico · 15%

**DÓNDE:** terminal local (usa `sshpbx`).
```bash
# El servicio TTS genera audio desde texto:
curl -s -X POST http://$PBX:8080/tts -H "Content-Type: application/json" \
  -d '{"texto":"Hola Juan, su cita de Cardiologia es el 2 de julio a las 10:30"}' \
  | python3 -c "import sys,json;d=json.load(sys.stdin);print('motor:',d['motor'],'| bytes:',d['bytes_audio'])"
# Audio personalizado de cada cita (formato Asterisk 8 kHz):
sshpbx 'soxi /var/lib/asterisk/sounds/citas/menu_3002.wav | grep -E "Channels|Sample Rate|Duration"'
```
**SE ESPERA:** `motor: gTTS(es-CL)` con audio > 50 000 bytes; WAV `1 canal, 8000 Hz`. El AGI reproduce
este audio en la llamada (`STREAM FILE`), visible en la traza con `agi set debug on`.

---

## 8. Dockerización

**DÓNDE:** terminal local (en tu PC, con Docker).
```bash
cd ~/Documentos/Duoc/ServUni/Examen/ENTREGA/03_Repositorio
docker build -f docker/Dockerfile -t clinica-pbx:eft .
docker run -d --name clinica-pbx clinica-pbx:eft
sleep 18
docker exec clinica-pbx asterisk -rx "pjsip show endpoints"   # 3001/3002/3003
docker exec clinica-pbx sqlite3 -column /var/lib/asterisk/agi-bin/citas.db "SELECT paciente_ext,nombre,estado FROM citas;"
docker stop clinica-pbx     # al terminar
```
**SE ESPERA:** la imagen construye; el contenedor levanta Asterisk con las 3 extensiones y la BD de citas.

---

## 9. Gestión del laboratorio (AWS)

**DÓNDE:** terminal local. Requiere credenciales del Cloud Labs vigentes en `~/.aws/credentials`.
```bash
# Ver instancias e IP:
aws ec2 describe-instances --region us-east-1 --query 'Reservations[].Instances[].{N:Tags[?Key==`Name`]|[0].Value,St:State.Name,IP:PublicIpAddress}' --output table
# Detener / arrancar (ahorrar tiempo de lab). IDs: PBX i-0e41f429e8bf80a9e, SBC i-0c29a4e6457089055, n8n i-062609b96f2ce1f75
aws ec2 stop-instances  --region us-east-1 --instance-ids i-0e41f429e8bf80a9e i-0c29a4e6457089055
aws ec2 start-instances --region us-east-1 --instance-ids i-0e41f429e8bf80a9e i-0c29a4e6457089055
```
> Tras **arrancar**, las IP públicas de PBX/SBC cambian. Actualiza la sección 0, regenera el cert del
> SBC (`sshsbc 'sudo bash /home/ubuntu/gen-cert.sh <IP_SBC> 172.31.57.212'`) y reapunta el flujo n8n a
> la nueva IP de la PBX (`PBX_API=http://<IP_PBX>:8080 python3 repo/n8n/build_workflow_citas.py`).
```
```
