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
    # === CAMBIO === Prompt_maestro más corto, fuerte y claro (para que mezcle tipos)
    st.session_state.prompt_maestro = """Eres un oficial del DOT real haciendo una inspección de carretera en Estados Unidos.

REGLAS OBLIGATORIAS (sigue en TODA respuesta):
- Usa inglés directo, seco y con prisa, como un oficial real.
- En cada frase del oficial usa varias palabras de la lista de vocabulario (prioridad absoluta).
- SIEMPRE mezcla en cada bloque: pregunta + indicación/comando + advertencia + señalamiento/hallazgo.
  NUNCA generes solo preguntas.
- Respuesta del camionero (EN_RES): siempre en inglés y máximo 4 palabras.
- Usa exactamente '###' entre cada bloque.
- No hagas oraciones largas del oficial.

FORMATO DE SALIDA EXACTO (no cambies nada):
ES: [Traducción literal al español de lo que dice el oficial]
EN: [Lo que dice el oficial en inglés]
EN_RES: [Respuesta corta del camionero en inglés]"""

# --- CONFIGURACIÓN API ---
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("Error: No se encontró GROQ_API_KEY en los secretos de Streamlit.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
MODELO_ACTUAL = "llama-3.3-70b-versatile"   # Mejor para esta tarea
# MODELO_ACTUAL = "llama-3.1-8b-instant"

async def generate_edge_audio(text, voice, filename):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- INTERFAZ ---
st.title("🚛 Trucker English Pro")

# --- BLOQUE DE EDICIÓN ---
with st.expander("⚙️ Editar Lista de Palabras y Prompt"):
    st.session_state.lista_palabras = st.text_area(
        "Tu Lista de Vocabulario:",
        value=st.session_state.lista_palabras,
        height=200
    )
    st.session_state.prompt_maestro = st.text_area(
        "Instrucciones para la IA (Prompt):",
        value=st.session_state.prompt_maestro,
        height=180
    )
    st.info("Cualquier cambio aquí se aplicará en la siguiente generación.")

# --- GENERACIÓN ---
cantidad = st.slider("Frases a generar", 1, 15, 5)

if st.button("🚀 Generar Lecciones", use_container_width=True):
    # Limpiar archivos viejos
    for f in glob.glob("leccion_*.mp3"):
        try: os.remove(f)
        except: pass
   
    seed = random.randint(1, 1000000)
   
    # === CAMBIO === Nonce para romper caché de Groq + reforzar reglas
    nonce = f"Variación única ID: {seed} - {random.random():.12f}"

    # === CAMBIO === Prompt final limpio y reforzado
    prompt_final = f"""
{st.session_state.prompt_maestro}

Genera exactamente {cantidad} bloques.

PALABRAS CLAVE: {st.session_state.lista_palabras}

{nonce}

Importante: Mezcla siempre pregunta, indicación, advertencia y hallazgo en los bloques.
Nunca hagas solo preguntas. EN_RES siempre en inglés.
"""

    try:
        with st.spinner("IA generando lecciones..."):
            completion = client.chat.completions.create(
                model=MODELO_ACTUAL,
                messages=[{"role": "user", "content": prompt_final}],
                temperature=0.75,        # === CAMBIO === Más variedad
                top_p=0.95,
                frequency_penalty=0.4,   # === CAMBIO === Reduce repetición
                presence_penalty=0.4,
                seed=seed
            )

            texto_ia = completion.choices[0].message.content
            # === CAMBIO === Mejor separación de bloques
            bloques = [b.strip() for b in texto_ia.split('###') if b.strip() and "EN:" in b]

            for i, bloque in enumerate(bloques):
                # === CAMBIO === Búsqueda más flexible del formato exacto que quieres
                es_m = re.search(r"ES:\s*(.*?)(?=EN:|$)", bloque, re.DOTALL)
                en_m = re.search(r"EN:\s*(.*?)(?=EN_RES:|$)", bloque, re.DOTALL)
                res_m = re.search(r"EN_RES:\s*(.*)", bloque, re.DOTALL)

                if es_m and en_m and res_m:
                    es_t = es_m.group(1).strip()
                    en_t = en_m.group(1).strip()
                    res_t = res_m.group(1).strip()

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
                    audio_path = f"leccion_{i}.mp3"
                    final.export(audio_path, format="mp3")
                    st.audio(audio_path)
                else:
                    st.warning(f"Bloque {i+1} no tiene el formato correcto.")

    except Exception as e:
        st.error(f"Error: {e}")

# --- REPRODUCTOR MAESTRO ---
def mostrar_reproductor_bucle():
    archivos = glob.glob("leccion_*.mp3")
    if not archivos: return
    archivos.sort(key=lambda x: int(re.search(r'\d+', x).group()))
    st.divider()
    if st.button("🎧 Activar Bucle Maestro", use_container_width=True):
        with st.spinner("Uniendo audios..."):
            playlist = AudioSegment.empty()
            pausa_p = AudioSegment.silent(duration=2500)
            for f in archivos:
                playlist += AudioSegment.from_mp3(f) + pausa_p
           
            playlist.export("master.mp3", format="mp3")
            with open("master.mp3", "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
           
            st.markdown(f"""
                <div style="text-align:center; background:#262730; padding:20px; border-radius:10px; border:2px solid #4CAF50;">
                    <h3 style="color:#4CAF50;">Modo Camionero Activo</h3>
                    <audio controls loop autoplay style="width:100%;">
                        <source src="data:audio/mp3;base64,{b64}" type="audio/mp3">
                    </audio>
                </div>
            """, unsafe_allow_html=True)

mostrar_reproductor_bucle()
