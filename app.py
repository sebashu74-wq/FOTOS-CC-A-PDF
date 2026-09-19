import io
import re
import streamlit as st
from PIL import Image, ImageOps
import zxingcpp
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="Unificador Cédulas Colombia", page_icon="📄", layout="wide")

st.title("📄 Unificador de Cédula a PDF")

# Session state para mantener las rotaciones instantáneas
if "rot_frente" not in st.session_state:
    st.session_state.rot_frente = 0
if "rot_reverso" not in st.session_state:
    st.session_state.rot_reverso = 0

def comprimir_ultra_rapido(img, max_dim=750):
    """Aplica orientación EXIF inicial y comprime para velocidad máxima."""
    img = ImageOps.exif_transpose(img)
    if max(img.width, img.height) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img

def leer_pdf417_cedula(img):
    """
    Escanea el código de barras PDF417 de la cédula en los 4 ángulos.
    Retorna: (imagen_orientada_correctamente, nombre_persona, es_reverso)
    """
    for angulo in [0, 90, 180, 270]:
        img_rotada = img.rotate(angulo, expand=True) if angulo != 0 else img
        
        # Leer códigos usando zxing-cpp
        resultados = zxingcpp.read_barcodes(img_rotada)
        
        for res in resultados:
            if str(res.format) in ["BarcodeFormat.PDF417", "PDF417", "BarcodeFormat.Code128"]:
                try:
                    raw_data = res.text
                    
                    # Extraer texto legible (Nombres y Apellidos)
                    partes = [p for p in re.split(r'[\x00-\x1F\x7F-\xFF]+', raw_data) if len(p) > 2]
                    texto_limpio = " ".join(partes)
                    
                    # Buscar nombres en mayúsculas
                    coincidencias = re.findall(r'[A-ZÑÁÉÍÓÚ]{3,}', texto_limpio)
                    if len(coincidencias) >= 2:
                        nombre_completo = " ".join(coincidencias[:4])
                        return img_rotada, nombre_completo, True
                except Exception:
                    pass
                return img_rotada, "", True

    return img, "", False

def orientar_frente(img):
    """Asegura orientación horizontal para la cara frontal."""
    if img.height > img.width:
        img = img.rotate(270, expand=True)
    return img

def procesar_cedulas(img1_raw, img2_raw):
    """Clasifica, orienta automáticamente y extrae el nombre."""
    img1 = comprimir_ultra_rapido(img1_raw)
    img2 = comprimir_ultra_rapido(img2_raw)

    # Detectar reverso usando el código PDF417
    img1_ori, nombre1, es_reverso1 = leer_pdf417_cedula(img1)
    
    if es_reverso1:
        img_reverso_final = img1_ori
        img_frente_final = orientar_frente(img2)
        nombre_detectado = nombre1
    else:
        img2_ori, nombre2, es_reverso2 = leer_pdf417_cedula(img2)
        if es_reverso2:
            img_reverso_final = img2_ori
            img_frente_final = orientar_frente(img1)
            nombre_detectado = nombre2
        else:
            img_frente_final = orientar_frente(img1)
            img_reverso_final = orientar_frente(img2)
            nombre_detectado = ""

    if nombre_detectado:
        nombre_pdf = f"Cedula {nombre_detectado}.pdf"
    else:
        nombre_pdf = "Cedula Documento.pdf"

    return img_frente_final, img_reverso_final, nombre_pdf

# --- INTERFAZ STREAMLIT ---
col_izq, col_der = st.columns([2, 1])

img_frente_raw = None
img_reverso_raw = None

with col_der:
    st.subheader("📤 Cargar Imágenes")
    modo = st.radio("Método de carga:", ["Arrastrar las 2 fotos juntas", "Subir por separado"])

    if modo == "Arrastrar las 2 fotos juntas":
        archivos = st.file_uploader("Selecciona o arrastra las 2 imágenes aquí", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        if archivos and len(archivos) == 2:
            with st.spinner("Procesando lectura rápida..."):
                i1 = Image.open(archivos[0])
                i2 = Image.open(archivos[1])
                img_frente_raw, img_reverso_raw, nombre_pdf_sugerido = procesar_cedulas(i1, i2)
    else:
        f_file = st.file_uploader("1. Cédula Frente (Arriba)", type=["jpg", "jpeg", "png"])
        r_file = st.file_uploader("2. Cédula Trasera (Abajo)", type=["jpg", "jpeg", "png"])
        if f_file and r_file:
            i1 = Image.open(f_file)
            i2 = Image.open(r_file)
            img_frente_raw, img_reverso_raw, nombre_pdf_sugerido = procesar_cedulas(i1, i2)

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
            label=f"📥 Descargar {nombre_pdf_sugerido}",
            data=pdf_buffer,
            file_name=nombre_pdf_sugerido,
            mime="application/pdf",
            type="primary",
            use_container_width=True
        )
    else:
        st.info("👈 Utiliza el panel de la derecha para arrastrar o subir las 2 imágenes de la cédula.")
