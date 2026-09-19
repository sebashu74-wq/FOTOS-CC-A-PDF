import io
import re
import streamlit as st
from PIL import Image, ImageOps
import pytesseract
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="Unificador de Cédulas", page_icon="📄", layout="wide")

st.title("📄 Unificador de Cédula a PDF")

# Inicializar estados de rotación
if "rot_frente" not in st.session_state:
    st.session_state.rot_frente = 0
if "rot_reverso" not in st.session_state:
    st.session_state.rot_reverso = 0

def comprimir_y_orientar_rapido(img):
    """Corrige la orientación EXIF, reduce resolución a máx 800px para velocidad extrema."""
    img = ImageOps.exif_transpose(img)
    if img.height > img.width:
        img = img.rotate(270, expand=True)
    
    # Redimensionar agresivamente para eliminar demora de procesamiento
    max_dim = 800
    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        
    return img

def extraer_datos_y_clasificar(img1, img2):
    """Analiza las imágenes con OCR rápido para clasificar Frente/Trasera y obtener Nombre completo."""
    def obtener_texto(img):
        try:
            # Reducir imagen para OCR ultra rápido
            img_ocr = img.copy()
            img_ocr.thumbnail((600, 600))
            return pytesseract.image_to_string(img_ocr, lang="spa").upper()
        except Exception:
            return ""

    txt1 = obtener_texto(img1)
    txt2 = obtener_texto(img2)

    palabras_frente = ["REPUBLICA", "IDENTIFICACION", "CEDULA", "NOMBRES", "APELLIDOS", "COLOMBIA"]
    score1 = sum(1 for p in palabras_frente if p in txt1)
    score2 = sum(1 for p in palabras_frente if p in txt2)

    if score1 >= score2:
        img_frente, img_trasera = img1, img2
        texto_frente = txt1
    else:
        img_frente, img_trasera = img2, img1
        texto_frente = txt2

    # Intentar extraer Nombre y Apellido
    nombre_archivo = "Cedula_Documento.pdf"
    try:
        lineas = [linea.strip() for linea in texto_frente.split("\n") if linea.strip()]
        nombres_encontrados = []
        
        for i, linea in enumerate(lineas):
            if "APELLIDOS" in linea and (i + 1) < len(lineas):
                nombres_encontrados.append(lineas[i + 1])
            elif "NOMBRES" in linea and (i + 1) < len(lineas):
                nombres_encontrados.append(lineas[i + 1])

        if nombres_encontrados:
            cadena_nombre = " ".join(nombres_encontrados)
            cadena_limpia = re.sub(r'[^A-ZÁÉÍÓÚÑ\s]', '', cadena_nombre).strip()
            if len(cadena_limpia) > 3:
                nombre_archivo = f"Cedula {cadena_limpia}.pdf"
    except Exception:
        pass

    return img_frente, img_trasera, nombre_archivo

# --- INTERFAZ DE USUARIO ---
col_izq, col_der = st.columns([2, 1])

img_frente_raw = None
img_reverso_raw = None

with col_der:
    st.subheader("📤 Cargar Imágenes")
    modo = st.radio("Método de carga:", ["Arrastrar las 2 fotos juntas", "Subir por separado"])

    if modo == "Arrastrar las 2 fotos juntas":
        archivos = st.file_uploader("Arrastra o selecciona las 2 imágenes aquí", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        if archivos and len(archivos) == 2:
            with st.spinner("Procesando y clasificando..."):
                i1 = Image.open(archivos[0])
                i2 = Image.open(archivos[1])
                img_frente_raw, img_reverso_raw, nombre_pdf_sugerido = extraer_datos_y_clasificar(i1, i2)
    else:
        f_file = st.file_uploader("1. Cédula Frente (Arriba)", type=["jpg", "jpeg", "png"])
        r_file = st.file_uploader("2. Cédula Trasera (Abajo)", type=["jpg", "jpeg", "png"])
        if f_file and r_file:
            img_frente_raw = Image.open(f_file)
            img_reverso_raw = Image.open(r_file)
            nombre_pdf_sugerido = "Cedula_Documento.pdf"

with col_izq:
    if img_frente_raw and img_reverso_raw:
        st.subheader("👁️ Vista Previa y Descarga")

        img_frente = comprimir_y_orientar_rapido(img_frente_raw)
        img_reverso = comprimir_y_orientar_rapido(img_reverso_raw)

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**1. Frente (Parte Superior)**")
            b1, b2 = st.columns(2)
            if b1.button("🔄 Girar 90°", key="f_90"):
                st.session_state.rot_frente = (st.session_state.rot_frente + 90) % 360
            if b2.button("🙃 Voltear 180°", key="f_180"):
                st.session_state.rot_frente = (st.session_state.rot_frente + 180) % 360

            img_frente_final = img_frente.rotate(360 - st.session_state.rot_frente, expand=True)
            st.image(img_frente_final, use_container_width=True)

        with c2:
            st.markdown("**2. Trasera (Parte Inferior)**")
            b3, b4 = st.columns(2)
            if b3.button("🔄 Girar 90°", key="r_90"):
                st.session_state.rot_reverso = (st.session_state.rot_reverso + 90) % 360
            if b4.button("🙃 Voltear 180°", key="r_180"):
                st.session_state.rot_reverso = (st.session_state.rot_reverso + 180) % 360

            img_reverso_final = img_reverso.rotate(360 - st.session_state.rot_reverso, expand=True)
            st.image(img_reverso_final, use_container_width=True)

        st.markdown("---")

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
            img.convert("RGB").save(buffer_temp, format="JPEG", quality=65)
            buffer_temp.seek(0)

            c.drawImage(ImageReader(buffer_temp), pos_x, pos_y, width=nuevo_ancho, height=nuevo_alto)

        agregar_imagen(img_frente_final, alto_pagina * 0.75)
        agregar_imagen(img_reverso_final, alto_pagina * 0.25)

        c.save()
        pdf_buffer.seek(0)

        # BOTÓN ÚNICO DIRECTO DE DESCARGA
        st.download_button(
            label=f"📥 Descargar {nombre_pdf_sugerido}",
            data=pdf_buffer,
            file_name=nombre_pdf_sugerido,
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    else:
        st.info("👈 Utiliza el panel de la derecha para cargar las dos imágenes.")
