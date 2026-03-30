import os
import re
import random
import asyncio
import edge_tts
import glob
import base64
import streamlit as st  # Corregido: Importación necesaria para usar 'st'
from groq import Groq
from pydub import AudioSegment
from gtts import gTTS

# --- CONFIGURACIÓN TÉCNICA ---
# Nota: En Streamlit Cloud (Linux), no necesitas poner ".exe" a ffprobe
AudioSegment.ffprobe = "ffprobe" 

st.set_page_config(page_title="Trucker English Editor", page_icon="🚛", layout="centered")

# --- CONEXIÓN SEGURA CON LA API (PASO 1) ---
# Aquí es donde el código se conecta con lo que configuraste en el "Punto 4"
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("⚠️ No se encontró la clave GROQ_API_KEY en los Secrets de Streamlit.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
MODELO_ACTUAL = "llama-3.3-70b-versatile"

# --- MEMORIA DE SESIÓN ---
if 'lista_palabras' not in st.session_state:
    st.session_state.lista_palabras = """A, all, am, an, and, any, are, at, beams, binder, box, BOL, bill, of, load, unload, been, brake, cab, can, card, CDL, charged, chassis, check, checked, city, clean, coming, going, go, clear, commercial, complete, compliance, compliant, container, cracked, cracks, current, cuts, damage, DVIR, days, did, do, does, down, driver, DOT, eight, ELD, road, roadside, electronic, email, emergency, equipment, everything, extinguisher, file, fine, fire, flat, fluid, flush, for, found, full, fuses, gauge, give, glass, glove, going, good, handy, have, here, high, holding, horn, hours, how, I, identification, in, inspect, inspection, insurance, is, it, know, last, leaks, left, license, lights, locked, locks, looking, openn, closee, drownw, hubb, logs, low, me, medical, menu, mode, morning, my, number, need, no, now, okay, on, or, output, outside, paperwork, parking, permit, alcohol, drugs, substances, issues, please, problem, pressure, pre-trip, properly, push, put, registration, release, reverse, right, rims, running, safe, screen, seatbelt, secured, see, send, service, shape, show, sidewall, signs, signal, sitting, solid, spare, step, sure, switching, system, tail, test, flat, mirror, engine, testing, the, there, them, through, tight, tire, tires, to, today, transfer, transmit, travel, tread, triangles, truck, turn, unit, up, over, give, valid, vehicle, via, why, washer, where, will, windshield, wipers, with, work, working, yes, you, your, zone, off, when, was, inspection, last, on, what, which, how, pull-off"""

if 'prompt_maestro' not in st.session_state:
    st.session_state.prompt_maestro = """Actúa como un oficial del DOT en una inspección de carretera real en Estados Unidos. Tu objetivo es generar bloques de práctica de inglés para un camionero.

REGLAS DE ORO:
1. Lenguaje Real: Usa inglés hablado, directo y a veces seco. No uses frases de libro de texto. Habla como un oficial con prisa.
2. Vocabulario Obligatorio: Debes seleccionar palabras de forma aleatoria de esta lista y darles prioridad absoluta en las frases.
3. Respuestas Cortas: El camionero debe responder con un máximo de 4 palabras. La claridad es más importante que la gramática perfecta.
4. Variedad de Situaciones: Cambia el enfoque en cada bloque (revisión de ELD, frenos, luces, carga, alcohol/drogas, pesaje o papelería).
5. Separador Obligatorio: Usa '###' estrictamente entre cada bloque.

FORMATO DE SALIDA:
ES: [Frase en español]
EN: [Lo que dice el oficial en inglés]
RES: [Respuesta corta del camionero en inglés]."""

async def generate_edge_audio(text, voice, filename):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- INTERFAZ ---
st.title("🚛 Trucker English Pro")

with st.expander("⚙️ Editar Lista de Palabras y Prompt"):
    st.session_state.lista_palabras = st.text_area("Tu Lista de Vocabulario:", value=st.session_state.lista_palabras, height=200)
    st.session_state.prompt_maestro = st.text_area("Instrucciones para la IA (Prompt):", value=st.session_state.prompt_maestro, height=150)

cantidad = st.slider("Frases a generar", 1, 15, 5)

if st.button("🚀 Generar Lecciones", use_container_width=True):
    for f in glob.glob("leccion_*.mp3"):
        try: os.remove(f)
        except: pass
    
    seed = random.randint(1, 100000)
    prompt_final = f"""
    {st.session_state.prompt_maestro}
    CANTIDAD: {cantidad} bloques.
    REGLA: Usa separador '###'.
    PALABRAS CLAVE: {st.session_state.lista_palabras}
    ID: {seed}
    """

    try:
        with st.spinner("IA generando contenido y audio..."):
            completion = client.chat.completions.create(
                model=MODELO_ACTUAL,
                messages=[{"role": "user", "content": prompt_final}]
            )

            texto_ia = completion.choices[0].message.content
            bloques = [b for b in texto_ia.split('###') if "EN:" in b]

            for i, bloque in enumerate(bloques):
                es_m = re.search(r"ES:(.*)", bloque)
                en_m = re.search(r"EN:(.*)", bloque)
                res_m = re.search(r"RES:(.*)", bloque)

                if es_m and en_m and res_m:
                    es_t, en_t, res_t = es_m.group(1).strip(), en_m.group(1).strip(), res_m.group(1).strip()
                    
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

    except Exception as e:
        st.error(f"Error: {e}")

def mostrar_reproductor_bucle():
    archivos = glob.glob("leccion_*.mp3")
    if not archivos: return
    archivos.sort(key=lambda x: int(re.search(r'\d+', x).group()))

    st.divider()
    if st.button("🎧 Activar Bucle Maestro", use_container_width=True):
        with st.spinner("Uniendo archivos..."):
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
