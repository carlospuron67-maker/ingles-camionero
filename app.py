import streamlit as st
import os
import re
import random
import asyncio
import edge_tts
import glob
import base64
from groq import Groq
from pydub import AudioSegment
from gtts import gTTS

# --- CONFIGURACIÓN TÉCNICA ---
AudioSegment.ffprobe = "ffprobe.exe"
st.set_page_config(page_title="Trucker English Editor", page_icon="🚛", layout="centered")

# --- MEMORIA DE SESIÓN ---
if 'lista_palabras' not in st.session_state:
    st.session_state.lista_palabras = """A, all, am, an, and, any, are, at, axle, beams, binder, box, BOL, bill, of, load,slop, inspection bay, lot, parking bay, parking space, pull-off, unload, been, brake, cab, can, card, CDL, charged, chassis, check, city, clean, clear, commercial, complete, compliance, compliant, container, cracked, cracks, current, cuts, damage, DVIR, days, did, do, does, down, driver, DOT, eight, ELD, electronic, email, emergency, equipment, everything, extinguisher, fifth-wheel, file, fine, fire, flat, fluid, flush, for, found, full, fuses, gauge, give, glass, glove, go, good, handy, have, here, high, holding, horn, hours, how, I, identification, in, inspect, insurance, is, it, know, landing-gear, last, leaks, left, license, lights, locked, logs, low, me, medical, menu, mirror, mode, morning, my, number, need, no, now, okay, on, open, or, output, outside, over, paperwork, parking, permit, alcohol, drugs, substances, issues, please, problem, pressure, pre-trip, properly, pull-off, push, put, registration, release, reverse, right, rims, road, roadside, running, safe, screen, seatbelt, secured, see, send, service, shape, show, sidewall, signs, signal, sitting, solid, spare, step, sure, switching, system, tail, tandem, test, the, there, them, through, tight, tire, today, transfer, transmit, travel, tread, triangles, truck, turn, unit, up, valid, vehicle, via, washer, was, what, when, where, which, why, will, windshield, wipers, with, work, yes, you, your, zone"""

if 'prompt_maestro' not in st.session_state:
    st.session_state.prompt_maestro = """Eres un oficial del DOT real haciendo una inspección de carretera en Estados Unidos.

REGLAS OBLIGATORIAS (CRÍTICAS):
- Usa inglés directo, seco y con prisa.
- Cada bloque DEBE incluir: pregunta + comando + advertencia + hallazgo.
- NO generes solo preguntas.

TRADUCCIÓN (OBLIGATORIO Y ESTRICTO):
- ES debe ser traducción EXACTA, COMPLETA y literal de EN.
- NO resumir, NO omitir, NO interpretar.
- TODO lo que esté en EN debe aparecer en ES.
- Mantén el mismo orden de ideas.
- Si EN tiene varias oraciones, ES debe tener las mismas.
- Prohibido acortar.

RESPUESTA DEL CAMIONERO:
- EN_RES: máximo 4 palabras.

FORMATO OBLIGATORIO:
ES: [traducción completa y literal]
EN: [texto original del oficial]
EN_RES: [respuesta corta]

SEPARADOR:
Usa exactamente ### entre bloques.
"""

# --- CONFIGURACIÓN API ---
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("Error: No se encontró GROQ_API_KEY en los secretos de Streamlit.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
MODELO_ACTUAL = "llama-3.3-70b-versatile"

# --- VALIDACIÓN DE TRADUCCIÓN ---
def validar_traduccion(es, en):
    # Si la traducción es demasiado corta, probablemente está incompleta
    if len(es) < len(en) * 0.7:
        return False
    return True

async def generate_edge_audio(text, voice, filename):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- INTERFAZ ---
st.title("🚛 Trucker English Pro")

with st.expander("⚙️ Editar Lista de Palabras y Prompt"):
    st.session_state.lista_palabras = st.text_area(
        "Tu Lista de Vocabulario:",
        value=st.session_state.lista_palabras,
        height=200
    )
    st.session_state.prompt_maestro = st.text_area(
        "Prompt:",
        value=st.session_state.prompt_maestro,
        height=250
    )

cantidad = st.slider("Frases a generar", 1, 15, 5)

if st.button("🚀 Generar Lecciones", use_container_width=True):

    for f in glob.glob("leccion_*.mp3"):
        try: os.remove(f)
        except: pass

    seed = random.randint(1, 1000000)
    nonce = f"ID:{seed}-{random.random()}"

    prompt_final = f"""
{st.session_state.prompt_maestro}

Genera exactamente {cantidad} bloques.

PALABRAS: {st.session_state.lista_palabras}

{nonce}
"""

    try:
        with st.spinner("Generando..."):
            completion = client.chat.completions.create(
                model=MODELO_ACTUAL,
                messages=[{"role": "user", "content": prompt_final}],
                temperature=0.7,
                top_p=0.95,
                frequency_penalty=0.4,
                presence_penalty=0.4,
                seed=seed
            )

            texto_ia = completion.choices[0].message.content
            bloques = [b.strip() for b in texto_ia.split('###') if b.strip()]

            for i, bloque in enumerate(bloques):

                es_m = re.search(r"ES:\s*(.*?)(?=EN:|$)", bloque, re.DOTALL)
                en_m = re.search(r"EN:\s*(.*?)(?=EN_RES:|$)", bloque, re.DOTALL)
                res_m = re.search(r"EN_RES:\s*(.*)", bloque, re.DOTALL)

                if es_m and en_m and res_m:

                    es_t = es_m.group(1).strip()
                    en_t = en_m.group(1).strip()
                    res_t = res_m.group(1).strip()

                    # 🔥 VALIDACIÓN + CORRECCIÓN AUTOMÁTICA
                    if not validar_traduccion(es_t, en_t):

                        correction_prompt = f"""
Corrige la traducción.

EN:
{en_t}

ES actual:
{es_t}

INSTRUCCIONES:
- Traduce TODO el contenido.
- No omitas nada.
- Traducción literal.

Devuelve:
ES: ...
"""

                        correction = client.chat.completions.create(
                            model=MODELO_ACTUAL,
                            messages=[{"role": "user", "content": correction_prompt}],
                            temperature=0
                        )

                        nueva_es = correction.choices[0].message.content
                        match_es = re.search(r"ES:\s*(.*)", nueva_es, re.DOTALL)

                        if match_es:
                            es_t = match_es.group(1).strip()

                    st.subheader(f"Lección {i+1}")
                    st.write(f"🇪🇸 {es_t}")
                    st.write(f"🇺🇸 **{en_t}** | *{res_t}*")

                    voces = ['en-US-GuyNeural', 'en-US-AvaNeural', 'en-GB-SoniaNeural']
                    voz = random.choice(voces)

                    gTTS(es_t, lang='es').save("es.mp3")
                    asyncio.run(generate_edge_audio(en_t, voz, "q.mp3"))
                    asyncio.run(generate_edge_audio(res_t, voz, "a.mp3"))

                    a_es = AudioSegment.from_mp3("es.mp3")
                    a_q = AudioSegment.from_mp3("q.mp3")
                    a_a = AudioSegment.from_mp3("a.mp3")

                    pausa = AudioSegment.silent(duration=1000)

                    final = a_es + pausa + (a_q + pausa) * 5 + (a_a + pausa) * 5
                    path = f"leccion_{i}.mp3"
                    final.export(path, format="mp3")

                    st.audio(path)

                else:
                    st.warning(f"Bloque {i+1} mal formado")

    except Exception as e:
        st.error(f"Error: {e}")

# --- REPRODUCTOR ---
def mostrar_reproductor_bucle():
    archivos = glob.glob("leccion_*.mp3")
    if not archivos: return

    archivos.sort(key=lambda x: int(re.search(r'\d+', x).group()))

    if st.button("🎧 Bucle Maestro"):
        playlist = AudioSegment.empty()
        pausa = AudioSegment.silent(duration=2000)

        for f in archivos:
            playlist += AudioSegment.from_mp3(f) + pausa

        playlist.export("master.mp3", format="mp3")

        with open("master.mp3", "rb") as f:
            b64 = base64.b64encode(f.read()).decode()

        st.markdown(f"""
        <audio controls loop autoplay>
        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
        </audio>
        """, unsafe_allow_html=True)

mostrar_reproductor_bucle()
