import io
import streamlit as st
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="Unificador de Cédulas Ultra-Rápido", page_icon="📄", layout="wide")

st.title("📄 Unificador de Cédula a PDF")

# Inicializar estados de rotación
if "rot_frente" not in st.session_state:
    st.session_state.rot_frente = 0
if "rot_reverso" not in st.session_state:
    st.session_state.rot_reverso = 0

def optimizar_y_orientar(img):
    """Corrige la orientación EXIF, redimensiona y comprime para máxima velocidad."""
    img = ImageOps.exif_transpose(img)
    if img.height > img.width:
        img = img.rotate(270, expand=True)
    
    # Redimensionar si es extremadamente grande para acelerar el procesamiento
    max_dim = 1200
    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
        
    return img

def es_cara_frontal(img):
    """Detecta de forma ultrarrápida si la imagen es el frente analizando la distribución cromática/oscura (foto del rostro)."""
    img_gray = img.convert("L").resize((100, 100))
    pixels = list(img_gray.getdata())
    # Contar píxeles oscuros (típicos de la foto de perfil y cabello)
    oscuros = sum(1 for p in pixels if p < 70)
    return oscuros > 1500  # Umbral para detectar rostro frente a reverso

col_izq, col_der = st.columns([2, 1])

img_frente_raw = None
img_reverso_raw = None

with col_der:
    st.subheader("📤 Cargar Imágenes")
    modo = st.radio("Modalidad de carga:", ["Arrastrar las 2 fotos juntas", "Subir por separado"])

    if modo == "Arrastrar las 2 fotos juntas":
        archivos = st.file_uploader("Selecciona o arrastra las 2 imágenes aquí", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        if archivos and len(archivos) == 2:
            i1 = Image.open(archivos[0])
            i2 = Image.open(archivos[1])
            if es_cara_frontal(i1):
                img_frente_raw, img_reverso_raw = i1, i2
            else:
                img_frente_raw, img_reverso_raw = i2, i1
    else:
        f_file = st.file_uploader("1. Cédula Frente (Arriba)", type=["jpg", "jpeg", "png"])
        r_file = st.file_uploader("2. Cédula Trasera (Abajo)", type=["jpg", "jpeg", "png"])
        if f_file and r_file:
            img_frente_raw = Image.open(f_file)
            img_reverso_raw = Image.open(r_file)

with col_izq:
    if img_frente_raw and img_reverso_raw:
        st.subheader("👁️ Vista Previa y Corrección de Orientación")

        img_frente = optimizar_y_orientar(img_frente_raw)
        img_reverso = optimizar_y_orientar(img_reverso_raw)

        c1, c2 = st.columns(2)

        with c1:
            st.markdown("**Frente (Mitad Superior)**")
            b1, b2 = st.columns(2)
            if b1.button("🔄 Girar 90°", key="f_90"):
                st.session_state.rot_frente = (st.session_state.rot_frente + 90) % 360
            if b2.button("🙃 Voltear 180°", key="f_180"):
                st.session_state.rot_frente = (st.session_state.rot_frente + 180) % 360

            img_frente_final = img_frente.rotate(360 - st.session_state.rot_frente, expand=True)
            st.image(img_frente_final, use_container_width=True)

        with c2:
            st.markdown("**Trasera (Mitad Inferior)**")
            b3, b4 = st.columns(2)
            if b3.button("🔄 Girar 90°", key="r_90"):
                st.session_state.rot_reverso = (st.session_state.rot_reverso + 90) % 360
            if b4.button("🙃 Voltear 180°", key="r_180"):
                st.session_state.rot_reverso = (st.session_state.rot_reverso + 180) % 360

            img_reverso_final = img_reverso.rotate(360 - st.session_state.rot_reverso, expand=True)
            st.image(img_reverso_final, use_container_width=True)

        st.markdown("---")

        if st.button("🚀 Generar PDF Instantáneo", type="primary", use_container_width=True):
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
                img.convert("RGB").save(buffer_temp, format="JPEG", quality=80)
                buffer_temp.seek(0)

                c.drawImage(ImageReader(buffer_temp), pos_x, pos_y, width=nuevo_ancho, height=nuevo_alto)

            agregar_imagen(img_frente_final, alto_pagina * 0.75)
            agregar_imagen(img_reverso_final, alto_pagina * 0.25)

            c.save()
            pdf_buffer.seek(0)

            st.success("¡PDF generado en milisegundos!")
            st.download_button(
                label="📥 Descargar PDF",
                data=pdf_buffer,
                file_name="cedula_completa.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    else:
        st.info("👈 Utiliza el panel de la derecha para subir o arrastrar ambas imágenes.")
