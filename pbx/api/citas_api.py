#!/usr/bin/env python3
"""
citas_api.py — API REST mínima de la base de datos de citas de la
Clínica Regional "Salud Integral" (EFT CUY5132).

Expone la BD SQLite que usa el AGI, para que el flujo n8n pueda
consultarla y actualizarla por HTTP.  Solo stdlib (sin dependencias).

Endpoints:
  GET  /health                 -> {"status":"ok"}
  GET  /citas                  -> lista de todas las citas
  GET  /citas/<ext>            -> ficha de la cita del paciente <ext>
  POST /citas/<ext>/estado     -> body {"estado":"CONFIRMADA"} actualiza estado

Uso:  python3 citas_api.py 8080
"""
import sqlite3, json, sys, base64, subprocess, tempfile, os
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

DB = "/var/lib/asterisk/agi-bin/citas.db"

def tts_mp3(texto):
    """Genera audio MP3 desde texto. gTTS (es-CL) con fallback espeak-ng.
    Devuelve (bytes_mp3, motor)."""
    tmp = tempfile.mkdtemp()
    mp3 = os.path.join(tmp, "out.mp3")
    try:
        from gtts import gTTS
        gTTS(text=texto, lang="es", tld="cl").save(mp3)
        motor = "gTTS(es-CL)"
    except Exception:
        wav = os.path.join(tmp, "out.wav")
        subprocess.run(["espeak-ng", "-v", "es", "-s", "150", "-w", wav, texto],
                       check=True, capture_output=True)
        subprocess.run(["ffmpeg", "-y", "-i", wav, mp3], check=True, capture_output=True)
        motor = "espeak-ng(offline)"
    data = open(mp3, "rb").read()
    return data, motor

def query(ext=None):
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    if ext:
        rows = con.execute("SELECT * FROM citas WHERE paciente_ext=?", (ext,)).fetchall()
    else:
        rows = con.execute("SELECT * FROM citas ORDER BY paciente_ext").fetchall()
    con.close()
    return [dict(r) for r in rows]

def set_estado(ext, estado):
    con = sqlite3.connect(DB)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = con.execute("UPDATE citas SET estado=?, actualizado=? WHERE paciente_ext=?",
                      (estado, ts, ext))
    con.commit(); n = cur.rowcount; con.close()
    return n

class Handler(BaseHTTPRequestHandler):
    server_version = "ClinicaSaludIntegral-CitasAPI/1.0"
    def _send(self, code, obj):
        body = json.dumps(obj, ensure_ascii=False, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        p = self.path.rstrip("/")
        if p in ("/health", "/healthz"):
            return self._send(200, {"status": "ok", "servicio": "API Citas Clinica Salud Integral"})
        if p == "/citas":
            return self._send(200, {"total": len(query()), "citas": query()})
        if p.startswith("/citas/"):
            ext = p.split("/")[2]
            r = query(ext)
            if r:
                return self._send(200, r[0])
            return self._send(404, {"error": f"sin cita para {ext}"})
        self._send(404, {"error": "ruta no encontrada"})

    def do_POST(self):
        parts = self.path.strip("/").split("/")
        if self.path.rstrip("/") == "/tts":
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            texto = body.get("texto", "")
            if not texto:
                return self._send(400, {"error": "falta 'texto'"})
            try:
                audio, motor = tts_mp3(texto)
            except Exception as e:
                return self._send(500, {"error": f"TTS fallo: {e}"})
            return self._send(200, {
                "ok": True, "motor": motor, "caracteres": len(texto),
                "bytes_audio": len(audio), "formato": "audio/mpeg",
                "audio_base64": base64.b64encode(audio).decode()})
        if len(parts) == 3 and parts[0] == "citas" and parts[2] == "estado":
            ext = parts[1]
            n = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(n) or b"{}")
            estado = body.get("estado", "PENDIENTE")
            updated = set_estado(ext, estado)
            if updated:
                return self._send(200, {"ext": ext, "estado": estado, "actualizado": True})
            return self._send(404, {"error": f"sin cita para {ext}"})
        self._send(404, {"error": "ruta no encontrada"})

    def log_message(self, fmt, *args):
        sys.stderr.write("[API-Citas] %s - %s\n" % (self.address_string(), fmt % args))

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    print(f"API Citas escuchando en 0.0.0.0:{port}  (BD: {DB})")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()
