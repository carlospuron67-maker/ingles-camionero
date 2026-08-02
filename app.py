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
    st.session_state.lista_palabras = """license, registration, insurance, logbook, hours of service, ELD, electronic logging device, weigh station, DOT number, trailer, axle, brakes, inspection, violation, ticket, citation, warning, fine, speed limit, cargo, freight, load, overweight, permit, route, GPS, fatigue, rest stop, fuel, toll, border, customs, manifest, hazmat, tires, tread, seatbelt, mirror, blind spot, merge, highway, checkpoint, breathalyzer, sober, license plate, VIN, dock, forklift, pallet, dispatcher, delivery, schedule, detour, construction zone, chain law, ice, snow, black ice, emergency, breakdown, roadside assistance, tow truck, officer, trooper, patrol, court, appeal, CDL, commercial driver's license, endorsement, medical card, drug test, alcohol, pre-trip inspection, post-trip inspection, headlights, taillights, turn signal, windshield, wiper, fire extinguisher, triangle, reflector, coupling, fifth wheel, jackknife, tarp, straps, chains, bill of lading, shipper, receiver, dock worker, layover, sleeper berth, off-duty, on-duty, driving time, break, pull over, step out, license and registration, destination, origin"""

if 'prompt_maestro' not in st.session_state:
    st.session_state.prompt_maestro = """Actúa como un oficial de policía / inspector de DOT (Department of Transportation) que detiene a un camionero en carretera para una inspección de rutina o una parada de tráfico.
Tu objetivo: Crear bloques de práctica siguiendo un patrón ESTRICTO.

REGLAS DE ORO:
1. Vocabulario: Usa palabras de la lista proporcionada (términos de camionero: licencia, carga, horas de manejo, inspección, etc.).
2. Estilo: Inglés directo, seco, autoritario y rápido, como lo hablaría un oficial real en una parada de tráfico.
3. Cada pregunta u orden del oficial debe tener su respuesta adecuada del camionero.

REGLA ANTI-REPETICIÓN: Genera preguntas totalmente nuevas y aleatorias usando la lista de palabras. No empieces siempre con las mismas preguntas.
REGLA: En cada generación nueva de pregunta y respuesta, incluir al menos dos de las siguientes preguntas/situaciones típicas:
1-License and registration, please.-Here you go, officer. My license, registration, and insurance.
2-Where are you coming from and where are you headed?-I'm coming from Denver, heading to Chicago with a full load.
3-How many hours have you been driving today?-I've been driving for about six hours. My logbook is up to date.
4-What are you hauling today?-I'm hauling general freight, fully secured and within weight limits.
5-I need to see your logbook and your ELD.-Sure, here's my logbook. Everything is logged electronically too.
6-Pull into the weigh station up ahead.-Yes sir, pulling in now.
7-Step out of the truck, please, for a quick inspection.-No problem, officer. Stepping out now.

REGLA DE IDIOMA (MUY IMPORTANTE):
- La línea "EN:" DEBE estar completamente en inglés.
- La línea "RES:" DEBE estar completamente en inglés (es la respuesta del camionero al oficial). NUNCA generes "RES:" en español.
- Solo la línea "ES:" va en español, como traducción de "EN:".

REGLA DE TRADUCCIÓN (MUY IMPORTANTE):
La línea "ES:" DEBE ser una traducción exacta, natural y fiel de la línea "EN:" (mismo significado, mismo tono).
- Usa español latino natural, como lo hablaría un hispanohablante nativo (evita calcos literales del inglés).
- No agregues ni quites información: el significado de ES y EN debe ser idéntico.
- Evita traducciones robóticas o demasiado formales; que suene a conversación real.

FORMATO DE SALIDA (Usa exactamente '###' para separar bloques):
ES: [Traducción natural y fiel al español de la línea EN]
EN: [Pregunta u orden del oficial, en inglés]
RES: [Respuesta corta del camionero, en inglés, entre 4 y 8 palabras]
###"""


# --- CONFIGURACIÓN API (MODIFICADO ÚNICAMENTE PARA SECRETOS) ---
if "GROQ_API_KEY" in st.secrets:
    GROQ_API_KEY = st.secrets["GROQ_API_KEY"]
else:
    st.error("Error: No se encontró GROQ_API_KEY en los secretos de Streamlit.")
    st.stop()

client = Groq(api_key=GROQ_API_KEY)

MODELOS_DISPONIBLES = {
    "GPT-OSS 120B (OpenAI, vía Groq)": "openai/gpt-oss-120b",
    "Llama 3.1 8B Instant (más rápido, menos preciso)": "llama-3.1-8b-instant",
    "Llama 3.3 70B Versatile (más preciso, más lento)": "llama-3.3-70b-versatile",
}

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

# --- NUEVO: OPCIÓN DE POSICIÓN DEL AUDIO EN ESPAÑOL (ES) ---
st.markdown("**🎚️ Posición de la traducción (ES) dentro de cada lección**")
orden_es = st.radio(
    "¿Dónde quieres escuchar la frase en español?",
    ["Al principio", "Al final", "Personalizado"],
    horizontal=True
)

pos_personalizada = 1
if orden_es == "Personalizado":
    pos_personalizada = st.number_input(
        "Reproducir el ES después del audio número:",
        min_value=1,
        max_value=20,
        value=1,
        step=1,
        help="Ej: 1 = después del primer audio (la pregunta). 2 = después del segundo audio, etc. "
             "Si el número es mayor a la cantidad de audios de la lección, el ES se pondrá al final."
    )

# --- NUEVO: SELECCIÓN DE MODELO DE IA ---
modelo_elegido_label = st.selectbox(
    "🤖 Modelo de IA",
    list(MODELOS_DISPONIBLES.keys()),
    index=0
)
MODELO_ACTUAL = MODELOS_DISPONIBLES[modelo_elegido_label]

# --- NUEVO: CANTIDAD DE VOCES DISTINTAS PARA LA PREGUNTA (OFICIAL) ---
cantidad_voces = st.slider(
    "🎙️ Cantidad de voces distintas para la pregunta en inglés",
    min_value=1,
    max_value=12,
    value=3,
    help="Cuántos acentos/voces distintas leerán la frase del oficial en cada lección, uno tras otro."
)

if st.button("🚀 Generar Lecciones", use_container_width=True):
    # Limpiar archivos viejos
    for f in glob.glob("leccion_*.mp3"):
        try: os.remove(f)
        except: pass
    
    # --- LÓGICA DE SELECCIÓN ALEATORIA (SOLO 60 PALABRAS) ---
    palabras_full = [p.strip() for p in st.session_state.lista_palabras.split(',') if p.strip()]
    palabras_seleccionadas = random.sample(palabras_full, min(len(palabras_full), 60))
    lista_para_api = ", ".join(palabras_seleccionadas)
    
    seed = random.randint(1, 100000)
    
    # Construcción dinámica del prompt usando solo las 60 palabras seleccionadas
    prompt_final = f"""
    {st.session_state.prompt_maestro}
    CANTIDAD: {cantidad} bloques.
    REGLA: Usa separador '###'.
    
LISTA DE PALABRAS (Prioridad): {lista_para_api}


    FORMATO:
    ES: [traducción natural y fiel al español de la línea EN]
    EN: [frase del oficial en inglés según el tipo: pregunta, comando, advertencia o hallazgo]
    RES: [respuesta corta del camionero, EN INGLÉS, entre 4 y 8 palabras. NUNCA en español]
    
    PALABRAS CLAVE PARA USAR: {lista_para_api}
    ID de variación: {seed}
    """

    try:
        with st.spinner("IA grabando audios..."):
            completion = client.chat.completions.create(
                model=MODELO_ACTUAL,
                messages=[
                    {
                        "role": "system", 
                        "content": "You are a strict Principal School. You MUST follow the requested pattern Question, without exception. Do not repeat types. Be dry and direct."
                    },
                    {
                        "role": "user", 
                        "content": prompt_final
                    }
                ],
                temperature=0.4
            )

            # --- 1. PROCESAMIENTO DE TEXTO ---
            texto_ia = completion.choices[0].message.content
            bloques = [b for b in texto_ia.split('###') if "EN:" in b]

            # --- 2. DEFINICIÓN DE VOCES (IMPORTANTE: Debe estar aquí arriba) ---
            voces_maestras = [
                'en-US-AndrewNeural', 'en-US-BrianNeural', 'en-US-ChristopherNeural', 
                'en-US-EricNeural', 'en-US-GuyNeural', 'en-US-JennyNeural', 
                'en-US-AvaNeural', 'en-US-MichelleNeural', 'en-GB-SoniaNeural', 
                'en-GB-RyanNeural', 'en-AU-WilliamNeural', 'en-CA-LiamNeural'
            ]

            # --- 3. BUCLE PRINCIPAL DE LECCIONES ---
            for i, bloque in enumerate(bloques):
                es_m = re.search(r"ES:(.*)", bloque)
                en_m = re.search(r"EN:(.*)", bloque)
                res_m = re.search(r"RES:(.*)", bloque)

                if es_m and en_m and res_m:
                    es_t, en_t, res_t = es_m.group(1).strip(), en_m.group(1).strip(), res_m.group(1).strip()
                    
                    st.subheader(f"Lección {i+1}")
                    st.write(f"🇪🇸 {es_t}")
                    st.write(f"🇺🇸 **{en_t}** | *{res_t}*")

                    # Audio en español
                    gTTS(es_t, lang='es').save("es.mp3")
                    a_es = AudioSegment.from_mp3("es.mp3")
                    pausa = AudioSegment.silent(duration=1000)

                    # Seleccionamos la cantidad de voces distintas elegida por el usuario
                    voces_leccion = random.sample(voces_maestras, min(len(voces_maestras), cantidad_voces))

                    # --- NUEVO: en vez de acumular en dos bloques fijos (preguntas/respuestas),
                    # construimos una lista ordenada de "clips" para poder insertar el ES
                    # en la posición que el usuario elija.
                    audio_clips = []  # cada elemento ya trae su pausa incluida

                    # --- BUCLE INTERNO: EL OFICIAL REPITE CON TODAS SUS VOCES SEGUIDAS ---
                    for v_idx, voz_elegida in enumerate(voces_leccion):
                        f_q = f"q_{v_idx}.mp3"

                        # OFICIAL: Se graban y añaden todas las voces distintas, una tras otra
                        asyncio.run(generate_edge_audio(en_t, voz_elegida, f_q))
                        audio_clips.append(AudioSegment.from_mp3(f_q) + pausa)

                    # CAMIONERO: Grabamos la respuesta una sola vez (con la primera voz de la lección)
                    f_a = "res_camionero.mp3"
                    asyncio.run(generate_edge_audio(res_t, voces_leccion[0], f_a))
                    respuesta_clip = AudioSegment.from_mp3(f_a) + pausa

                    # La respuesta se repite 3 veces, al final de las preguntas
                    for _ in range(3):
                        audio_clips.append(respuesta_clip)

                    # --- NUEVO: Insertar el clip de ES en la posición elegida ---
                    es_clip = a_es + pausa

                    if orden_es == "Al principio":
                        pos_insercion = 0
                    elif orden_es == "Al final":
                        pos_insercion = len(audio_clips)
                    else:  # Personalizado
                        # Se limita para no salirse del rango disponible
                        pos_insercion = min(pos_personalizada, len(audio_clips))

                    audio_clips.insert(pos_insercion, es_clip)

                    # Unión final de la lección respetando el orden con ES incluido
                    final = AudioSegment.empty()
                    for clip in audio_clips:
                        final += clip
                    
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
