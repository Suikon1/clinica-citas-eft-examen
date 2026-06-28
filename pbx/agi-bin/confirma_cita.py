#!/usr/bin/env python3
"""
confirma_cita.py — Script AGI del Sistema de Confirmación Automática de Citas
Clínica Regional "Salud Integral"  ·  EFT CUY5132

Flujo:
  1. Atiende la llamada (el dialplan ya hizo Answer()).
  2. Consulta la cita del paciente en la BD SQLite (clave = extensión marcada).
  3. Reproduce un mensaje TTS personalizado (nombre, especialidad, médico,
     fecha y hora) generado con gTTS/espeak.
  4. Captura la respuesta DTMF del paciente:
        1 = Confirmar     2 = Cancelar     3 = Reprogramar
  5. Actualiza el estado de la cita en la BD.
  6. Registra el resultado en el log de confirmaciones.
Comunicación con Asterisk vía protocolo AGI (stdin/stdout).
"""
import sys, os, csv, sqlite3, subprocess
from datetime import datetime

DB       = "/var/lib/asterisk/agi-bin/citas.db"
SND_DIR  = "/var/lib/asterisk/sounds/citas"
LOG      = "/var/log/asterisk/citas_confirmacion.log"
CSVLOG   = "/var/lib/asterisk/agi-bin/confirmaciones.csv"

ACCIONES = {"1": ("CONFIRMADA",   "Su cita ha sido confirmada. Muchas gracias. Le esperamos."),
            "2": ("CANCELADA",    "Su cita ha sido cancelada. Gracias por avisar."),
            "3": ("REPROGRAMAR",  "Su solicitud de reprogramación fue registrada. Le contactaremos pronto.")}

# ---------------------------------------------------------------- AGI helpers
def agi_read_env():
    env = {}
    while True:
        line = sys.stdin.readline()
        if not line or line.strip() == "":
            break
        if ":" in line:
            k, v = line.split(":", 1)
            env[k.strip()] = v.strip()
    return env

def agi(cmd):
    sys.stdout.write(cmd + "\n"); sys.stdout.flush()
    return sys.stdin.readline().strip()

def verbose(msg, level=1):
    agi(f'VERBOSE "{msg}" {level}')

def stream(file_noext, escape="\"\""):
    """STREAM FILE; devuelve el dígito presionado (char) o '' si ninguno."""
    r = agi(f'STREAM FILE {file_noext} "{escape}"')
    # respuesta: 200 result=<ascii> endpos=...
    try:
        val = int(r.split("result=")[1].split(" ")[0])
        return chr(val) if val > 0 else ""
    except Exception:
        return ""

def wait_digit(timeout_ms=7000):
    r = agi(f'WAIT FOR DIGIT {timeout_ms}')
    try:
        val = int(r.split("result=")[1].split(" ")[0])
        return chr(val) if val > 0 else ""
    except Exception:
        return ""

# ------------------------------------------------------------------- negocio
def log_evento(texto):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        with open(LOG, "a") as f:
            f.write(f"[{ts}] {texto}\n")
    except Exception:
        pass
    verbose(f"CITAS: {texto}")

def get_cita(ext):
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    row = con.execute("SELECT * FROM citas WHERE paciente_ext=?", (ext,)).fetchone()
    con.close()
    return row

def update_estado(ext, estado):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    con = sqlite3.connect(DB)
    con.execute("UPDATE citas SET estado=?, actualizado=? WHERE paciente_ext=?",
                (estado, ts, ext))
    con.commit(); con.close()

def registrar_csv(ext, cita, estado, digito):
    nuevo = not os.path.exists(CSVLOG)
    with open(CSVLOG, "a", newline="") as f:
        w = csv.writer(f)
        if nuevo:
            w.writerow(["timestamp","ext","nombre","especialidad","fecha","hora","dtmf","estado"])
        w.writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), ext,
                    cita["nombre"], cita["especialidad"], cita["fecha"],
                    cita["hora"], digito, estado])

def tts_wav(text, outbase):
    """Genera <outbase>.wav (8kHz mono). gTTS con fallback espeak-ng."""
    mp3, wav = outbase + ".mp3", outbase + ".wav"
    try:
        from gtts import gTTS
        gTTS(text=text, lang="es", tld="cl").save(mp3)
        subprocess.run(["ffmpeg","-y","-i",mp3,"-ar","8000","-ac","1",
                        "-acodec","pcm_s16le",wav], check=True, capture_output=True)
        os.remove(mp3)
    except Exception:
        raw = outbase + "_raw.wav"
        subprocess.run(["espeak-ng","-v","es","-s","150","-w",raw,text],
                       check=True, capture_output=True)
        subprocess.run(["ffmpeg","-y","-i",raw,"-ar","8000","-ac","1",
                        "-acodec","pcm_s16le",wav], check=True, capture_output=True)
        os.remove(raw)
    return outbase

def mensaje_menu(c):
    return (f"Estimado paciente {c['nombre']}. Le saluda la Clínica Regional "
            f"Salud Integral. Le recordamos su cita de {c['especialidad']} con "
            f"{c['medico']}, el día {c['fecha']} a las {c['hora']} horas. "
            f"Para confirmar presione 1. Para cancelar presione 2. "
            f"Para reprogramar presione 3.")

# ---------------------------------------------------------------------- main
def main():
    env = agi_read_env()
    ext = sys.argv[1] if len(sys.argv) > 1 else env.get("agi_arg_1", env.get("agi_callerid",""))
    log_evento(f"=== Inicio confirmación  paciente_ext={ext}  canal={env.get('agi_channel','?')}")

    cita = get_cita(ext)
    if not cita:
        log_evento(f"Sin cita registrada para {ext}")
        agi('STREAM FILE invalid ""')
        return

    # 1) Mensaje TTS personalizado (pre-generado en seed; regenerar si falta)
    menu = os.path.join(SND_DIR, f"menu_{ext}")
    if not os.path.exists(menu + ".wav"):
        try:
            tts_wav(mensaje_menu(cita), menu)
            log_evento(f"TTS regenerado on-the-fly para {ext}")
        except Exception as e:
            log_evento(f"ERROR TTS ({e}); uso prompts estándar")
            menu = None

    # 2) Reproducir y capturar DTMF (interrumpible por 1/2/3)
    digito = ""
    intentos = 0
    while not digito and intentos < 2:
        if menu:
            digito = stream(menu, "123")
        else:
            agi('STREAM FILE vm-enter-num-to-call "123"')
        if not digito:
            digito = wait_digit(7000)
        intentos += 1

    # 3) Resolver acción
    if digito in ACCIONES:
        estado, despedida = ACCIONES[digito]
        update_estado(ext, estado)
        registrar_csv(ext, cita, estado, digito)
        log_evento(f"Paciente {cita['nombre']} ({ext}) presionó {digito} -> {estado}")
        try:
            bye = tts_wav(despedida, "/tmp/bye_%s" % ext)
            agi(f'STREAM FILE {bye} ""')
        except Exception:
            agi('STREAM FILE vm-goodbye ""')
    else:
        update_estado(ext, "SIN_RESPUESTA")
        registrar_csv(ext, cita, "SIN_RESPUESTA", "-")
        log_evento(f"Paciente {cita['nombre']} ({ext}) sin respuesta DTMF (timeout)")
        agi('STREAM FILE vm-goodbye ""')

    log_evento(f"=== Fin confirmación  paciente_ext={ext}  resultado={digito or 'timeout'}")

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        try:
            log_evento(f"EXCEPCION: {e}")
        except Exception:
            pass
        sys.exit(0)
