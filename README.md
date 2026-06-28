# Sistema de Confirmación Automática de Citas — Clínica Regional "Salud Integral"

**EFT CUY5132 · Comunicaciones Unificadas · Duoc UC**

Solución de telefonía IP que realiza llamadas automáticas para confirmar citas médicas,
captura la respuesta del paciente por DTMF, actualiza la base de datos y notifica a
recepción. Incluye seguridad perimetral (SBC + TLS) y un agente conversacional con IA y TTS.

## Arquitectura

| Componente | Tecnología | Rol |
|---|---|---|
| **PBX** | Asterisk 18 (PJSIP) | Central telefónica, AGI de citas, BD SQLite, TTS, API REST |
| **SBC** | Kamailio 5.5 | Borde de sesión: TLS, enrutamiento, ocultamiento de topología |
| **Orquestador** | n8n + OpenRouter (IA) | Webhook → consulta BD → IA → TTS → Slack |
| **Cloud** | AWS IaaS (us-east-1) | VMs + Security Groups (aislamiento de la PBX) |

Diagrama completo: `../evidencias/ev-arquitectura.png`

## Estructura del repositorio

```
pbx/
  etc-asterisk/pjsip.conf        Extensiones SIP (3001/3002/3003) en PJSIP
  etc-asterisk/extensions.conf   Plan de marcado: internal, citas, sim-paciente
  agi-bin/confirma_cita.py       Script AGI: TTS + DTMF + BD + log
  db/seed_citas.py               Inicializa la BD SQLite y genera los audios TTS
  api/citas_api.py               API REST de citas (consulta/actualiza BD) + endpoint TTS
  test-softphones.sh             Registra 3 softphones (baresip) para pruebas
  test-agi-citas.sh              Prueba reproducible del AGI (responde 1/2/3)
sbc/
  kamailio.cfg                   Configuración del SBC (proxy + TLS + topology hiding)
  tls.cfg                        Perfil TLS del SBC
  gen-cert.sh                    Genera el certificado TLS de la clínica
n8n/
  workflow-confirmacion-citas.json   Flujo n8n exportado
  build_workflow_citas.py            Script que crea/activa el flujo vía API
docker/
  Dockerfile / entrypoint.sh / docker-compose.yml   PBX dockerizada
```

## Despliegue rápido (PBX dockerizada)

```bash
cd docker
docker compose up -d --build       # construye e inicia la central
docker exec clinica-pbx asterisk -rx "pjsip show endpoints"
```

## Extensiones SIP

| Ext | Rol | Clave |
|---|---|---|
| 3001 | Sistema de confirmación | Clinica.3001 |
| 3002 | Paciente / prueba | Clinica.3002 |
| 3003 | Recepción / prueba | Clinica.3003 |

## Flujo de confirmación

1. El sistema llama al paciente (o el paciente marca el servicio).
2. El AGI consulta la cita en la BD y reproduce un mensaje **TTS personalizado**
   (nombre, especialidad, médico, fecha, hora).
3. El paciente responde por DTMF: **1** Confirmar · **2** Cancelar · **3** Reprogramar.
4. El AGI actualiza el estado en la BD y registra el resultado (log + CSV).
5. El flujo n8n consulta la BD, genera el recordatorio con IA, sintetiza el audio (TTS)
   y notifica a recepción por Slack.

## Seguridad

- Los **Security Groups** aíslan la PBX: solo acepta SIP/RTP desde el SBC.
- Solo el **SBC** se expone a Internet; reenruta a la PBX y oculta su IP privada.
- La señalización SIP viaja cifrada por **TLS 1.3** (puerto 5061), verificado con `tshark`.

> Trabajo académico desarrollado sobre infraestructura de laboratorio autorizada (AWS Academy).
