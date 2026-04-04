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
#AudioSegment.converter = "ffmpeg.exe"
AudioSegment.ffprobe = "ffprobe.exe"

st.set_page_config(page_title="Trucker English Editor", page_icon="🚛", layout="centered")

# --- MEMORIA DE SESIÓN (Para no perder cambios al recargar) ---
if 'lista_palabras' not in st.session_state:
    st.session_state.lista_palabras = """A, all, am, an, and, any, are, at, axle, beams, binder, box, BOL, bill, of, load,slop, inspection bay, lot, parking bay, parking space, pull-off, unload, been, brake, cab, can, card, CDL, charged, chassis, check, city, clean, clear, commercial, complete, compliance, compliant, container, cracked, cracks, current, cuts, damage, DVIR, days, did, do, does, down, driver, DOT, eight, ELD, electronic, email, emergency, equipment, everything, extinguisher, fifth-wheel, file, fine, fire, flat, fluid, flush, for, found, full, fuses, gauge, give, glass, glove, go, good, handy, have, here, high, holding, horn, hours, how, I, identification, in, inspect, insurance, is, it, know, landing-gear, last, leaks, left, license, lights, locked, logs, low, me, medical, menu, mirror, mode, morning, my, number, need, no, now, okay, on, open, or, output, outside, over, paperwork, parking, permit, alcohol, drugs, substances, issues, please, problem, pressure, pre-trip, properly, pull-off, push, put, registration, release, reverse, right, rims, road, roadside, running, safe, screen, seatbelt, secured, see, send, service, shape, show, sidewall, signs, signal, sitting, solid, spare, step, sure, switching, system, tail, tandem, test, the, there, them, through, tight, tire, today, transfer, transmit, travel, tread, triangles, truck, turn, unit, up, valid, vehicle, via, washer, was, what, when, where, which, why, will, windshield, wipers, with, work, yes, you, your, zone"""

if 'prompt_maestro' not in st.session_state:
    st.session_state.prompt_maestro = """Actúa como un oficial del DOT real haciendo una inspección de carretera en Estados Unidos. Tu objetivo es crear práctica de inglés hablado para un camionero hispanohablante.

REGLAS DE ORO (sigue todas estrictamente):

1. Lenguaje Real: Usa inglés directo, seco, hablado y con prisa, como un oficial real en la carretera. Nada de lenguaje formal , de libro o cursos.

2. Vocabulario Obligatorio: En cada frase o leccion que diga el oficial, selecciona al azar varias palabras de esta "lista de palabras" definidas anteriormente y dales prioridad ABSOLUTA. Intégralas de forma natural siempre que sea posible:


3. Alterna la lecciones o frases a partes iguales con:
   - Preguntas
   - Indicaciones y orientaciones ("Pull over", "Show me", "Step out")
   - Advertencias ("That's a violation")
   - Señalamientos y hallazgos ("I see cracks", "Brakes are worn", "Leaking fluid")

4. Respuesta del camionero: Máximo 4 palabras. Prioriza claridad sobre gramática perfecta.

5. Separador: Usa exactamente '###' entre cada bloque. Nada más.

6- Lo expresado por el oficia DOT no debe ser oraciones largas

FORMATO DE SALIDA EXACTO (no cambies nada):

ES: [Lo expresado por el oficial del DOT ]
EN: [Lo que dice el oficial en inglés usando palabras de la lista]
EN_RES: [Respuesta corta del camionero en inglés - máximo 4 palabras]."""


# --- CONFIGURACIÓN API (MODIFICADO ÚNICAMENTE PARA SECRETOS) ---
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("Error: No se encontró GROQ_API_KEY en los secretos de Streamlit.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)
MODELO_ACTUAL = "llama-3.3-70b-versatile"
#MODELO_ACTUAL = "llama-3.1-8b-instant"

async def generate_edge_audio(text, voice, filename):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(filename)

# --- INTERFAZ ---
st.title("🚛 Trucker English Pro")

# --- BLOQUE DE EDICIÓN (EXPANDER) ---
with st.expander("⚙️ Editar Lista de Palabras y Prompt"):
    st.session_state.lista_palabras = st.text_area(
        "Tu Lista de Vocabulario:", 
        value=st.session_state.lista_palabras, 
        height=200
    )
    st.session_state.prompt_maestro = st.text_area(
        "Instrucciones para la IA (Prompt):", 
        value=st.session_state.prompt_maestro, 
        height=150
    )
    st.info("Cualquier cambio aquí se aplicará en la siguiente generación.")

# --- GENERACIÓN ---
cantidad = st.slider("Frases a generar", 1, 15, 5)

if st.button("🚀 Generar Lecciones", use_container_width=True):
    # Limpiar archivos viejos
    for f in glob.glob("leccion_*.mp3"):
        try: os.remove(f)
        except: pass
    
    seed = random.randint(1, 100000)
    
   #  Construcción dinámica del prompt
    prompt_final = f"""
    {st.session_state.prompt_maestro}
    CANTIDAD: {cantidad} bloques.
    REGLA: Usa separador '###'.
    FORMATO:
    ES: [frase en español]
    EN: [pregunta en inglés]
    RES: [respuesta corta en inglés]
    
    PALABRAS CLAVE PARA USAR: {st.session_state.lista_palabras}
    ID de variación: {seed}
    """

    try:
        with st.spinner("IA grabando audios..."):
            completion = client.chat.completions.create(
                model=MODELO_ACTUAL,
                #messages=[{"role": "user", "content": prompt_final}],
                messages=[
    {"role": "system", "content": "You are a strict translator. Follow instructions exactly. No summarizing."},
    {"role": "user", "content": prompt_final + f"\n\nUNIQUE_RUN_ID:{random.random()}"}
],
                temperature=0.2
            )
    #================================================================================================

    #===============================================================================================

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

                    a_es, a_q, a_a = AudioSegment.from_mp3("es.mp3"), AudioSegment.from_mp3("q.mp3"), AudioSegment.from_mp3("a.mp3")
                    pausa = AudioSegment.silent(duration=1000)
                    
                    final = a_es + pausa + (a_q + pausa) * 5 + (a_a + pausa) * 5
                    audio_path = f"leccion_{i}.mp3"
                    final.export(audio_path, format="mp3")
                    st.audio(audio_path)

    except Exception as e:
        st.error(f"Error: {e}")

# --- REPRODUCTOR MAESTRO ---
def mostrar_reproductor_bucle():
    archivos = glob.glob("leccion_*.mp3")
    if not archivos: return
    archivos.sort(key=lambda x: int(re.search(r'\d+', x).group()))

    st.divider()
    if st.button("🎧 Activar Bucle Maestro", use_container_width=True):
        with st.spinner("Uniendo..."):
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
