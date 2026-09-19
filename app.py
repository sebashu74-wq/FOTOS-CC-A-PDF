import io
import streamlit as st
from PIL import Image, ImageOps
import pytesseract
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="Unificador de Cédulas IA", page_icon="📄", layout="wide")

st.title("📄 Unificador de Cédula a PDF")

def orientar_imagen_inteligente(img):
    """Corrige automáticamente la orientación mediante EXIF y análisis OCR."""
    # 1. Orientación EXIF (cámara)
    img = ImageOps.exif_transpose(img)
    
    # 2. Corrección OCR si la imagen viene en ángulo (0, 90, 180, 270)
    try:
        data = pytesseract.image_to_osd(img)
        rot_angle = int(data.split("Rotate: ")[1].split("\n")[0])
        if rot_angle != 0:
            img = img.rotate(360 - rot_angle, expand=True)
    except Exception:
        pass  # Si falla el OCR, conserva la orientación original
        
    # 3. Asegurar orientación horizontal (Cédula horizontal)
    if img.height > img.width:
        img = img.rotate(270, expand=True)
        
    return img

def detectar_frente_y_reverso(img1, img2):
    """Detecta automáticamente cuál imagen es el frente y cuál es la trasera mediante texto."""
    def obtener_texto(img):
        try:
            return pytesseract.image_to_string(img).upper()
        except Exception:
            return ""

    texto1 = obtener_texto(img1)
    texto2 = obtener_texto(img2)

    palabras_frente = ["REPUBLICA", "IDENTIDAD", "CEDULA", "NOMBRES", "APELLIDOS", "NACIMIENTO", "SEXO"]
    score1 = sum(1 for p in palabras_frente if p in texto1)
    score2 = sum(1 for p in palabras_frente if p in texto2)

    if score1 >= score2:
        return img1, img2
    else:
        return img2, img1

# --- DISEÑO DE LA INTERFAZ EN COLUMNAS ---
col_izquierda, col_derecha = st.columns([2, 1])

img_frente = None
img_reverso = None

with col_derecha:
    st.subheader("📤 Cargar Imágenes")
    
    modo_carga = st.radio("Método de carga:", ["Separado", "Subir los 2 juntos (Auto-detectar)"])
    
    if modo_carga == "Separado":
        frente_file = st.file_uploader("1. Cédula Frente (Arriba)", type=["jpg", "jpeg", "png"], key="frente")
        reverso_file = st.file_uploader("2. Cédula Trasera (Abajo)", type=["jpg", "jpeg", "png"], key="reverso")
        
        if frente_file and reverso_file:
            img_frente = Image.open(frente_file)
            img_reverso = Image.open(reverso_file)
    else:
        archivos_juntos = st.file_uploader("Subir las 2 fotos al mismo tiempo", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="juntos")
        if archivos_juntos and len(archivos_juntos) == 2:
            img1 = Image.open(archivos_juntos[0])
            img2 = Image.open(archivos_juntos[1])
            with st.spinner("Identificando Frente y Reverso..."):
                img_frente, img_reverso = detectar_frente_y_reverso(img1, img2)

with col_izquierda:
    if img_frente and img_reverso:
        st.subheader("👁️ Vista previa y ajustes")
        
        # Procesar orientación inteligente
        with st.spinner("Optimizando orientación automática..."):
            img_frente = orientar_imagen_inteligente(img_frente)
            img_reverso = orientar_imagen_inteligente(img_reverso)

        c_prev1, c_prev2 = st.columns(2)
        
        with c_prev1:
            rot_frente = st.selectbox("Ajuste manual Frente", [0, 90, 180, 270], index=0)
            if rot_frente != 0:
                img_frente = img_frente.rotate(360 - rot_frente, expand=True)
            st.image(img_frente, caption="Frente (Mitad Superior)", use_container_width=True)

        with c_prev2:
            rot_reverso = st.selectbox("Ajuste manual Trasera", [0, 90, 180, 270], index=0)
            if rot_reverso != 0:
                img_reverso = img_reverso.rotate(360 - rot_reverso, expand=True)
            st.image(img_reverso, caption="Trasera (Mitad Inferior)", use_container_width=True)

        st.markdown("---")
        
        if st.button("🚀 Generar y Descargar PDF", type="primary", use_container_width=True):
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

            # Insertar en el PDF
            agregar_imagen(img_frente, alto_pagina * 0.75)
            agregar_imagen(img_reverso, alto_pagina * 0.25)
            
            c.save()
            pdf_buffer.seek(0)

            st.success("¡PDF generado con éxito!")
            st.download_button(
                label="📥 Descargar PDF",
                data=pdf_buffer,
                file_name="cedula_completa.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    else:
        st.info("👈 Selecciona o sube los dos archivos de imagen en el panel de la derecha para comenzar.")
