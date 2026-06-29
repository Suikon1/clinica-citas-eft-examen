# Guion del video demostrativo (máx. 5 min) — EFT CUY5132

Sistema de Confirmación de Citas · Clínica "Salud Integral". Graba pantalla (OBS / `Ctrl+Alt+Shift+R` de GNOME) y narra. Los comandos ya están con las **IP actuales** del lab.

> **IP actuales** (cambian si reinicias el lab): PBX `100.26.56.46` · SBC `54.210.44.135` · n8n `https://18-213-161-67.nip.io`.
> Conexión SSH: `ssh -i ~/Documentos/Duoc/ServUni/Examen/lab.pem ubuntu@<IP>`

---

### Escena 1 — Introducción y arquitectura (0:00–0:30)
- **Muestra:** el diagrama `02_Evidencias/ev-arquitectura.png` a pantalla completa.
- **Narra:** «Sistema de confirmación automática de citas para la Clínica Salud Integral. En AWS: una PBX Asterisk privada, un SBC Kamailio que la protege con TLS, y n8n para la orquestación con IA, voz y Slack.»

### Escena 2 — Extensiones SIP y llamada interna · Ind. 1 (0:30–1:15)
```bash
ssh -i lab.pem ubuntu@100.26.56.46
sudo asterisk -rx "pjsip show contacts"          # 3001/3002/3003 en estado Avail
sudo asterisk -rx "channel originate PJSIP/3002 extension 3003@internal"
sudo asterisk -rx "core show channels"           # canales Up (llamada activa)
```
- **Narra:** «Las tres extensiones PJSIP están registradas. Lanzo una llamada interna 3002→3003: se establece correctamente.»

### Escena 3 — AGI de confirmación: DTMF + BD + log · Ind. 2 (1:15–2:15)
```bash
# Estado inicial de las citas
sudo -u asterisk sqlite3 -column /var/lib/asterisk/agi-bin/citas.db \
  "SELECT paciente_ext,nombre,especialidad,fecha,hora,estado FROM citas;"
# Llamada automática: el paciente 3002 confirma (tecla 1)
sudo asterisk -rx "dialplan set global DIGITO 1"
sudo asterisk -rx "channel originate Local/3002@sim-paciente/n extension 3002@citas"
# (esperar ~12 s) — el AGI reproduce el mensaje TTS y captura el DTMF
sudo -u asterisk sqlite3 -column /var/lib/asterisk/agi-bin/citas.db \
  "SELECT paciente_ext,estado,actualizado FROM citas;"     # 3002 -> CONFIRMADA
sudo tail -n 5 /var/log/asterisk/citas_confirmacion.log    # log con el resultado
```
- **Narra:** «El sistema llama al paciente, reproduce un mensaje de voz con los datos de su cita y captura su respuesta por teclado. Presiona 1: la cita pasa a CONFIRMADA en la base de datos y queda registrada en el log. El 2 cancela y el 3 reprograma.»

### Escena 4 — SBC: aislamiento (Security Groups) y enrutamiento · Ind. 3 y 4 (2:15–3:00)
```bash
# Desde tu equipo (NO por SSH): la PBX NO es accesible desde Internet
nc -zv -w5 100.26.56.46 5060      # -> timeout (bloqueado)
nc -zv -w5 54.210.44.135 5060     # -> el SBC SÍ responde (abierto)
# Lógica de enrutamiento del SBC
ssh -i lab.pem ubuntu@54.210.44.135 "sudo sed -n '40,90p' /etc/kamailio/kamailio.cfg"
```
- **Narra:** «La PBX está aislada: solo acepta tráfico del SBC, nunca de Internet. El SBC es el único expuesto y reenvía la señalización a la PBX ocultando su dirección interna.» (Apóyate en `ev-ind3-01` y `ev-ind4-01`.)

### Escena 5 — TLS: señalización cifrada · Ind. 5 (3:00–3:45)
```bash
# El puerto público presenta el certificado de la clínica y cifra con TLS 1.3
openssl s_client -connect 54.210.44.135:5061 </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -dates
```
- **Muestra:** `ev-ind5-02` (5060 en texto plano legible vs 5061 cifrado e ilegible).
- **Narra:** «La señalización viaja cifrada con TLS 1.3. En el puerto sin cifrar se leen los datos del paciente; en el puerto seguro, solo datos cifrados ilegibles.»

### Escena 6 — Agente virtual n8n: webhook + IA + TTS + Slack · Ind. 6 y 7 (3:45–4:40)
- **Muestra:** la UI de n8n (`https://18-213-161-67.nip.io`, workflow «EFT - Confirmación de Citas»). Recorre el canvas.
```bash
# Dispara el flujo y muestra la respuesta
curl -sk -X POST https://18-213-161-67.nip.io/webhook/cita-confirmacion \
  -H "Content-Type: application/json" -d '{"ext":"3002"}' | python3 -m json.tool
```
- **Muestra:** en n8n pestaña *Executions* (todos los nodos verdes) y el mensaje publicado en el **canal de Slack**.
- **Narra:** «El webhook recibe al paciente, consulta la base de datos de citas, un agente de IA redacta el recordatorio, se sintetiza el audio con TTS y se notifica a recepción por Slack.»

### Escena 7 — Dockerización y cierre (4:40–5:00)
```bash
cd ~/Documentos/Duoc/ServUni/Examen/ENTREGA/03_Repositorio/docker
cat Dockerfile        # o muestra ev-docker-01
```
- **Narra:** «Toda la PBX está empaquetada en Docker para un despliegue reproducible. El código y la documentación están en el repositorio. Gracias.»

---

**Tips:** ten 2 terminales abiertas y el navegador en n8n antes de grabar; ensaya una vez; si una llamada tarda, corta el clip. Apunta a 4:30–4:50 para dejar margen.
