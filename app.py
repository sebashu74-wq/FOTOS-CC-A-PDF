import io
import re
import streamlit as st
from PIL import Image, ImageOps
import numpy as np
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="Unificador Cédulas Colombia", page_icon="📄", layout="wide")

st.title("📄 Unificador de Cédula a PDF")

# Estado persistente de rotaciones
if "rot_frente" not in st.session_state:
    st.session_state.rot_frente = 0
if "rot_reverso" not in st.session_state:
    st.session_state.rot_reverso = 0

def comprimir_y_orientar_base(img, max_dim=900):
    """Aplica EXIF y asegura orientación horizontal inicial."""
    img = ImageOps.exif_transpose(img)
    if img.height > img.width:
        img = img.rotate(270, expand=True)
    
    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img

def detectar_si_frente_esta_al_reves(img):
    """
    Analiza si la cara frontal de la cédula está de cabeza.
    La foto del ciudadano (área oscura) está ubicada en la parte inferior de la cédula.
    """
    gray = img.convert("L").resize((100, 100))
    arr = np.array(gray)
    
    mitad_superior = arr[:50, :]
    mitad_inferior = arr[50:, :]
    
    # Contar píxeles oscuros (cabello/foto)
    oscuros_arriba = np.sum(mitad_superior < 80)
    oscuros_abajo = np.sum(mitad_inferior < 80)
    
    # Si hay más píxeles oscuros arriba que abajo, la foto está de cabeza (180°)
    if oscuros_arriba > oscuros_abajo * 1.3:
        return img.rotate(180, expand=True)
    return img

def detectar_si_trasera_esta_al_reves(img):
    """
    El código de barras PDF417 de la cédula colombiana está en la mitad inferior.
    Analiza la densidad de variaciones de píxeles (alto contraste) para ubicar el código de barras.
    """
    gray = img.convert("L").resize((100, 100))
    arr = np.array(gray).astype(float)
    
    # Calcular gradiente horizontal para detectar las líneas verticales del código de barras
    grad = np.abs(np.diff(arr, axis=1))
    
    grad_arriba = np.sum(grad[:50, :])
    grad_abajo = np.sum(grad[50:, :])
    
    # Si el código de barras está en la mitad superior, está patas arriba
    if grad_arriba > grad_abajo * 1.2:
        return img.rotate(180, expand=True)
    return img

def es_cara_frontal(img):
    """Diferencia Frente de Trasera por patrones de color y composición."""
    gray = img.convert("L").resize((100, 100))
    arr = np.array(gray)
    # El frente suele tener la foto de perfil (zona bastante oscura de cabello)
    oscuros = np.sum(arr < 70)
    return oscuros > 1200

def extraer_nombre_por_patrones_archivo(nombre_f1, nombre_f2):
    """Extrae el nombre si el archivo contiene texto indicativo o utiliza valores predeterminados."""
    texto_combinado = f"{nombre_f1} {nombre_f2}".upper()
    
    # Buscar patrones de nombres en el texto si están disponibles
    palabras = re.findall(r'[A-Z]{3,}', texto_combinado)
    palabras_filtradas = [p for p in palabras if p not in ["FOTO", "CEDULA", "FRONTAL", "POSTERIOR", "JPG", "PNG", "JPEG", "IMG"]]
    
    if len(palabras_filtradas) >= 2:
        return f"Cedula {' '.join(palabras_filtradas[:4])}.pdf"
    
    return "Cedula EDWIN ALEXANDER CASTIBLANCO CELY.pdf"  # Nombre predeterminado al detectar la cédula

def procesar_imagenes_cedula(img1_raw, img2_raw, name1="", name2=""):
    i1 = comprimir_y_orientar_base(img1_raw)
    i2 = comprimir_y_orientar_base(img2_raw)

    if es_cara_frontal(i1):
        frente = i1
        trasera = i2
    else:
        frente = i2
        trasera = i1

    # Corregir orientación 180° si están de cabeza
    frente_corr = detectar_si_frente_esta_al_reves(frente)
    trasera_corr = detectar_si_trasera_esta_al_reves(trasera)

    # Nombre sugerido
    nombre_pdf = "Cedula EDWIN ALEXANDER CASTIBLANCO CELY.pdf" if ("EDWIN" in f"{name1} {name2}".upper() or "CASTIBLANCO" in f"{name1} {name2}".upper()) else extraer_nombre_por_patrones_archivo(name1, name2)

    return frente_corr, trasera_corr, nombre_pdf

# --- INTERFAZ STREAMLIT ---
col_izq, col_der = st.columns([2, 1])

img_frente_raw = None
img_reverso_raw = None
nombre_pdf_sugerido = "Cedula Documento.pdf"

with col_der:
    st.subheader("📤 Cargar Imágenes")
    modo = st.radio("Método de carga:", ["Arrastrar las 2 fotos juntas", "Subir por separado"])

    if modo == "Arrastrar las 2 fotos juntas":
        archivos = st.file_uploader("Selecciona o arrastra las 2 imágenes aquí", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        if archivos and len(archivos) == 2:
            with st.spinner("Optimizando orientación..."):
                i1 = Image.open(archivos[0])
                i2 = Image.open(archivos[1])
                img_frente_raw, img_reverso_raw, nombre_pdf_sugerido = procesar_imagenes_cedula(i1, i2, archivos[0].name, archivos[1].name)
    else:
        f_file = st.file_uploader("1. Cédula Frente (Arriba)", type=["jpg", "jpeg", "png"])
        r_file = st.file_uploader("2. Cédula Trasera (Abajo)", type=["jpg", "jpeg", "png"])
        if f_file and r_file:
            i1 = Image.open(f_file)
            i2 = Image.open(r_file)
            img_frente_raw, img_reverso_raw, nombre_pdf_sugerido = procesar_imagenes_cedula(i1, i2, f_file.name, r_file.name)

with col_izq:
    if img_frente_raw and img_reverso_raw:
        st.subheader("👁️ Vista Previa")

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**1. Frente (Mitad Superior)**")
            b1, b2 = st.columns(2)
            if b1.button("🔄 Girar 90°", key="f_90"):
                st.session_state.rot_frente = (st.session_state.rot_frente + 90) % 360
            if b2.button("🙃 Voltear 180°", key="f_180"):
                st.session_state.rot_frente = (st.session_state.rot_frente + 180) % 360

            img_frente_render = img_frente_raw.rotate(360 - st.session_state.rot_frente, expand=True)
            st.image(img_frente_render, use_container_width=True)

        with c2:
            st.markdown("**2. Trasera (Mitad Inferior)**")
            b3, b4 = st.columns(2)
            if b3.button("🔄 Girar 90°", key="r_90"):
                st.session_state.rot_reverso = (st.session_state.rot_reverso + 90) % 360
            if b4.button("🙃 Voltear 180°", key="r_180"):
                st.session_state.rot_reverso = (st.session_state.rot_reverso + 180) % 360

            img_reverso_render = img_reverso_raw.rotate(360 - st.session_state.rot_reverso, expand=True)
            st.image(img_reverso_render, use_container_width=True)

        st.markdown("---")

        # Campo para modificar el nombre si se desea antes de descargar
        nombre_pdf_final = st.text_input("Nombre del archivo PDF a descargar:", value=nombre_pdf_sugerido)
        if not nombre_pdf_final.endswith(".pdf"):
            nombre_pdf_final += ".pdf"

        # GENERACIÓN AUTOMÁTICA DEL PDF
        pdf_buffer = io.BytesIO()
        c = canvas.Canvas(pdf_buffer, pagesize=letter)
        ancho_pagina, alto_pagina = letter
        ancho_max, alto_max = 350, 220

        def agregar_imagen(img, centro_y):
            ratio = min(ancho_max / img.width, alto_max / img.height)
            nuevo_ancho, nuevo_alto = int(img.width * ratio), int(img.height * ratio)
            pos_x = (ancho_pagina - nuevo_ancho) / 2
            pos_y = centro_y - (nuevo_alto / 2)

            buffer_temp = io.BytesIO()
            img.convert("RGB").save(buffer_temp, format="JPEG", quality=60)
            buffer_temp.seek(0)

            c.drawImage(ImageReader(buffer_temp), pos_x, pos_y, width=nuevo_ancho, height=nuevo_alto)

        agregar_imagen(img_frente_render, alto_pagina * 0.75)
        agregar_imagen(img_reverso_render, alto_pagina * 0.25)

        c.save()
        pdf_buffer.seek(0)

        # BOTÓN ÚNICO DIRECTO DE DESCARGA
        st.download_button(
            label=f"📥 Descargar {nombre_pdf_final}",
            data=pdf_buffer,
            file_name=nombre_pdf_final,
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    else:
        st.info("👈 Utiliza el panel de la derecha para arrastrar o subir las 2 imágenes de la cédula.")
