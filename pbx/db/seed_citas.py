#!/usr/bin/env python3
"""
seed_citas.py — Crea e inicializa la base de datos de citas de la
Clínica Regional "Salud Integral" (EFT CUY5132) y pre-genera el audio
TTS personalizado de cada cita.

BD:   /var/lib/asterisk/agi-bin/citas.db   (SQLite)
Audio: /var/lib/asterisk/sounds/citas/menu_<ext>.wav   (8 kHz mono PCM)
"""
import sqlite3, os, sys, subprocess

DB   = "/var/lib/asterisk/agi-bin/citas.db"
SND  = "/var/lib/asterisk/sounds/citas"

# Cada cita se identifica por la extensión/ficha del paciente (clave de marcado)
CITAS = [
    # ext , nombre            , especialidad , medico            , fecha        , hora
    ("3001","Sistema Interno"  ,"Administración","-"              ,"-"           ,"-"   ),
    ("3002","Juan Perez Soto"  ,"Cardiología" ,"Dr. Andres Rojas","02-07-2026"  ,"10:30"),
    ("3003","Maria Gonzalez"   ,"Dermatología","Dra. Carla Rivas","03-07-2026"  ,"15:00"),
]

DDL = """
CREATE TABLE IF NOT EXISTS citas (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    paciente_ext  TEXT UNIQUE,
    nombre        TEXT,
    especialidad  TEXT,
    medico        TEXT,
    fecha         TEXT,
    hora          TEXT,
    estado        TEXT DEFAULT 'PENDIENTE',
    actualizado   TEXT
);
"""

def tts_wav(text, outbase):
    """Genera <outbase>.wav (8 kHz mono) desde texto. gTTS (es-CL) con
    fallback a espeak-ng offline. Devuelve la ruta sin extensión."""
    mp3, wav = outbase + ".mp3", outbase + ".wav"
    try:
        from gtts import gTTS
        gTTS(text=text, lang="es", tld="cl").save(mp3)
        subprocess.run(["ffmpeg","-y","-i",mp3,"-ar","8000","-ac","1",
                        "-acodec","pcm_s16le",wav],
                       check=True, capture_output=True)
        os.remove(mp3)
        motor = "gTTS(es-CL)"
    except Exception as e:
        sys.stderr.write(f"[gTTS no disponible: {e}] usando espeak-ng\n")
        raw = outbase + "_raw.wav"
        subprocess.run(["espeak-ng","-v","es","-s","150","-w",raw,text],
                       check=True, capture_output=True)
        subprocess.run(["ffmpeg","-y","-i",raw,"-ar","8000","-ac","1",
                        "-acodec","pcm_s16le",wav],
                       check=True, capture_output=True)
        os.remove(raw)
        motor = "espeak-ng(offline)"
    return wav, motor

def mensaje_cita(c):
    nombre, esp, med, fecha, hora = c[1], c[2], c[3], c[4], c[5]
    return (f"Estimado paciente {nombre}. Le saluda la Clínica Regional "
            f"Salud Integral. Le recordamos su cita de {esp} con {med}, "
            f"el día {fecha} a las {hora} horas. "
            f"Para confirmar su asistencia, presione 1. "
            f"Para cancelar la cita, presione 2. "
            f"Para solicitar una reprogramación, presione 3.")

def main():
    os.makedirs(SND, exist_ok=True)
    con = sqlite3.connect(DB)
    con.execute(DDL)
    for c in CITAS:
        con.execute(
            "INSERT INTO citas(paciente_ext,nombre,especialidad,medico,fecha,hora,estado)"
            " VALUES(?,?,?,?,?,?, 'PENDIENTE')"
            " ON CONFLICT(paciente_ext) DO UPDATE SET"
            " nombre=excluded.nombre, especialidad=excluded.especialidad,"
            " medico=excluded.medico, fecha=excluded.fecha, hora=excluded.hora,"
            " estado='PENDIENTE'", c)
        if c[0] in ("3002","3003"):
            wav, motor = tts_wav(mensaje_cita(c), os.path.join(SND, f"menu_{c[0]}"))
            print(f"  TTS {c[0]} -> {wav}  [{motor}]")
    con.commit()
    print("\nContenido de la tabla citas:")
    for row in con.execute("SELECT paciente_ext,nombre,especialidad,fecha,hora,estado FROM citas"):
        print("  ", row)
    con.close()
    print(f"\nBD lista: {DB}")

if __name__ == "__main__":
    main()
