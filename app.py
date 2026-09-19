import io
import streamlit as st
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="Unificador de Cédulas", page_icon="📄")

st.title("📄 Unificador de Cédula a PDF")
st.write("Sube la parte frontal y trasera de la cédula para generar un PDF listo para imprimir.")

col1, col2 = st.columns(2)

with col1:
    frente_file = st.file_uploader("1. Cédula Frente", type=["jpg", "jpeg", "png"])
with col2:
    reverso_file = st.file_uploader("2. Cédula Trasera", type=["jpg", "jpeg", "png"])

if frente_file and reverso_file:
    # Cargar imágenes y corregir orientación EXIF automática
    img_frente = ImageOps.exif_transpose(Image.open(frente_file))
    img_reverso = ImageOps.exif_transpose(Image.open(reverso_file))
    
    # Asegurar que ambas queden horizontales si la foto se tomó vertical
    if img_frente.height > img_frente.width:
        img_frente = img_frente.rotate(270, expand=True)
    if img_reverso.height > img_reverso.width:
        img_reverso = img_reverso.rotate(270, expand=True)

    # Opciones manuales de rotación en caso de que vengan de cabeza
    st.subheader("⚙️ Ajuste de orientación (Opcional)")
    col_rot1, col_rot2 = st.columns(2)
    
    with col_rot1:
        rot_frente = st.selectbox("Girar Frente", [0, 90, 180, 270], index=0)
        if rot_frente != 0:
            img_frente = img_frente.rotate(360 - rot_frente, expand=True)
        st.image(img_frente, caption="Vista previa Frente", use_container_width=True)

    with col_rot2:
        rot_reverso = st.selectbox("Girar Trasera", [0, 90, 180, 270], index=0)
        if rot_reverso != 0:
            img_reverso = img_reverso.rotate(360 - rot_reverso, expand=True)
        st.image(img_reverso, caption="Vista previa Trasera", use_container_width=True)

    # Generación de PDF
    if st.button("🚀 Generar PDF"):
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
            img.convert("RGB").save(buffer_temp, format="JPEG")
            buffer_temp.seek(0)
            
            c.drawImage(ImageReader(buffer_temp), pos_x, pos_y, width=nuevo_ancho, height=nuevo_alto)

        # Ubicar mitad superior e inferior
        agregar_imagen(img_frente, alto_pagina * 0.75)
        agregar_imagen(img_reverso, alto_pagina * 0.25)
        
        c.save()
        pdf_buffer.seek(0)

        st.success("¡PDF generado correctamente!")
        st.download_button(
            label="📥 Descargar PDF",
            data=pdf_buffer,
            file_name="cedula_completa.pdf",
            mime="application/pdf"
        )
