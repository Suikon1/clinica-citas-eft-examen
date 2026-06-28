#!/usr/bin/env python3
"""
Crea (o actualiza) en n8n el workflow de Confirmación de Citas de la
Clínica Regional "Salud Integral" (EFT CUY5132) vía la API pública de n8n.

Flujo:
  Webhook (POST /cita-confirmacion)
     -> HTTP Request: API Citas (GET /citas/{ext})   [Ind.6 consulta BD]
     -> AI Agent (OpenRouter)  redacta recordatorio   [agente IA]
     -> HTTP Request: TTS (POST /tts)  genera audio    [Ind.7 TTS dinamico]
     -> Slack  notifica al canal de recepción          [integración Slack]
     -> Respond to Webhook  devuelve resultado
"""
import json, os, sys, urllib.request

N8N   = os.environ.get("N8N_URL", "https://18.213.161.67")
APIKEY= os.environ["N8N_API_KEY"]
PBXAPI= os.environ.get("PBX_API", "http://54.234.31.148:8080")
OPENROUTER_CRED = ("RHr67FrACgyHakV5", "OpenRouter Lab")
SLACK_CRED      = ("oRcQAJ7vnUxHor1H", "Slack Bot Olivaw")
SLACK_CHANNEL   = "C0BBNGC26FR"

def node(name, ntype, tv, params, pos, creds=None):
    n = {"parameters": params, "name": name, "type": ntype,
         "typeVersion": tv, "position": pos}
    if creds:
        n["credentials"] = creds
    return n

nodes = [
    node("Webhook Cita", "n8n-nodes-base.webhook", 2,
         {"httpMethod": "POST", "path": "cita-confirmacion",
          "responseMode": "responseNode", "options": {}},
         [-40, 300]),

    node("API Citas (consulta BD)", "n8n-nodes-base.httpRequest", 4.2,
         {"url": f"={PBXAPI}/citas/{{{{ $json.body.ext }}}}",
          "options": {}}, [200, 300]),

    node("AI Agent", "@n8n/n8n-nodes-langchain.agent", 1.7,
         {"promptType": "define",
          "text": "={{ 'Genera un recordatorio telefónico breve y cordial para esta cita médica. "
                  "Paciente: ' + $json.nombre + '. Especialidad: ' + $json.especialidad + '. Médico: ' + "
                  "$json.medico + '. Fecha: ' + $json.fecha + '. Hora: ' + $json.hora + '. "
                  "Incluye que debe presionar 1 para confirmar, 2 cancelar, 3 reprogramar.' }}",
          "options": {"systemMessage": "Eres el asistente virtual de la Clínica Regional Salud Integral. "
                      "Redactas recordatorios de citas claros, breves y empáticos, en español de Chile. "
                      "Máximo 2 frases."}},
         [440, 300]),

    node("OpenRouter Chat Model", "@n8n/n8n-nodes-langchain.lmChatOpenRouter", 1,
         {"model": "liquid/lfm-2.5-1.2b-instruct:free", "options": {}},
         [440, 520], {"openRouterApi": {"id": OPENROUTER_CRED[0], "name": OPENROUTER_CRED[1]}}),

    node("TTS (genera audio)", "n8n-nodes-base.httpRequest", 4.2,
         {"method": "POST", "url": f"{PBXAPI}/tts",
          "sendBody": True, "specifyBody": "json",
          "jsonBody": "={{ JSON.stringify({ texto: 'Estimado ' + $('API Citas (consulta BD)').item.json.nombre "
                      "+ '. Le recordamos su cita de ' + $('API Citas (consulta BD)').item.json.especialidad "
                      "+ ' el ' + $('API Citas (consulta BD)').item.json.fecha + ' a las ' "
                      "+ $('API Citas (consulta BD)').item.json.hora + ' horas.' }) }}",
          "options": {}}, [820, 300]),

    node("Slack Notifica Recepción", "n8n-nodes-base.slack", 2.5,
         {"resource": "message", "operation": "post", "select": "channel",
          "channelId": {"__rl": True, "mode": "id", "value": SLACK_CHANNEL},
          "text": "=:hospital: *Recordatorio de cita generado*\n"
                  "• Paciente: {{ $('API Citas (consulta BD)').item.json.nombre }}\n"
                  "• Especialidad: {{ $('API Citas (consulta BD)').item.json.especialidad }}\n"
                  "• Fecha: {{ $('API Citas (consulta BD)').item.json.fecha }} {{ $('API Citas (consulta BD)').item.json.hora }}\n"
                  "• Estado: {{ $('API Citas (consulta BD)').item.json.estado }}\n"
                  "• Audio TTS: {{ $json.bytes_audio }} bytes ({{ $json.motor }})",
          "otherOptions": {}}, [1180, 300],
         {"slackApi": {"id": SLACK_CRED[0], "name": SLACK_CRED[1]}}),

    node("Respond to Webhook", "n8n-nodes-base.respondToWebhook", 1.1,
         {"respondWith": "json",
          "responseBody": "={{ JSON.stringify({ ok: true, "
                          "cita: $('API Citas (consulta BD)').item.json, "
                          "recordatorio: $('AI Agent').item.json.output, "
                          "tts: { motor: $('TTS (genera audio)').item.json.motor, "
                          "bytes: $('TTS (genera audio)').item.json.bytes_audio } }) }}",
          "options": {}}, [1520, 300]),
]

connections = {
    "Webhook Cita": {"main": [[{"node": "API Citas (consulta BD)", "type": "main", "index": 0}]]},
    "API Citas (consulta BD)": {"main": [[{"node": "AI Agent", "type": "main", "index": 0}]]},
    "AI Agent": {"main": [[{"node": "TTS (genera audio)", "type": "main", "index": 0}]]},
    "OpenRouter Chat Model": {"ai_languageModel": [[{"node": "AI Agent", "type": "ai_languageModel", "index": 0}]]},
    "TTS (genera audio)": {"main": [[{"node": "Slack Notifica Recepción", "type": "main", "index": 0}]]},
    "Slack Notifica Recepción": {"main": [[{"node": "Respond to Webhook", "type": "main", "index": 0}]]},
}

workflow = {"name": "EFT - Confirmación de Citas (Clínica Salud Integral)",
            "nodes": nodes, "connections": connections,
            "settings": {"executionOrder": "v1"}}

def api(method, path, data=None):
    url = N8N + path
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, method=method,
            headers={"X-N8N-API-KEY": APIKEY, "Content-Type": "application/json", "accept": "application/json"})
    import ssl
    ctx = ssl.create_default_context(); ctx.check_hostname=False; ctx.verify_mode=ssl.CERT_NONE
    with urllib.request.urlopen(req, context=ctx) as r:
        return json.loads(r.read() or "{}")

if __name__ == "__main__":
    # ¿existe ya? -> borrar para recrear limpio
    existing = api("GET", "/api/v1/workflows")
    for w in existing.get("data", []):
        if w["name"] == workflow["name"]:
            print("Borrando workflow previo", w["id"])
            try: api("DELETE", f"/api/v1/workflows/{w['id']}")
            except Exception as e: print("  (no se pudo borrar:", e, ")")
    created = api("POST", "/api/v1/workflows", workflow)
    wid = created["id"]
    print("Workflow creado:", wid)
    api("POST", f"/api/v1/workflows/{wid}/activate")
    print("Workflow ACTIVADO")
    print("Webhook:", f"{N8N}/webhook/cita-confirmacion")
