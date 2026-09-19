import io
import streamlit as st
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader

st.set_page_config(page_title="Unificador de Cédulas Ultra-Rápido", page_icon="📄", layout="wide")

st.title("📄 Unificador de Cédulas a PDF (Rápido y Liviano)")

# Inicializar estados para rotaciones rápidas
if "rot_frente" not in st.session_state:
    st.session_state.rot_frente = 0
if "rot_reverso" not in st.session_state:
    st.session_state.rot_reverso = 0

def procesar_orientacion_basica(img):
    """Aplica orientación EXIF nativa y asegura vista horizontal."""
    img = ImageOps.exif_transpose(img)
    if img.height > img.width:
        img = img.rotate(270, expand=True)
    return img

col_izq, col_der = st.columns([2, 1])

with col_der:
    st.subheader("📤 Cargar Imágenes")
    
    frente_file = st.file_uploader("1. Cédula Frente (Arriba)", type=["jpg", "jpeg", "png"], key="u_frente")
    reverso_file = st.file_uploader("2. Cédula Trasera (Abajo)", type=["jpg", "jpeg", "png"], key="u_reverso")

with col_izq:
    if frente_file and reverso_file:
        st.subheader("👁️ Vista Previa y Corrección Directa")
        
        img_frente_base = procesar_orientacion_basica(Image.open(frente_file))
        img_reverso_base = procesar_orientacion_basica(Image.open(reverso_file))

        # Controles de rotación instantánea
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**Frente (Mitad Superior)**")
            r1, r2 = st.columns(2)
            if r1.button("🔄 Girar 90°", key="btn_f_90"):
                st.session_state.rot_frente = (st.session_state.rot_frente + 90) % 360
            if r2.button("🙃 Voltear 180°", key="btn_f_180"):
                st.session_state.rot_frente = (st.session_state.rot_frente + 180) % 360
                
            img_frente_final = img_frente_base.rotate(360 - st.session_state.rot_frente, expand=True)
            st.image(img_frente_final, use_container_width=True)

        with c2:
            st.markdown("**Trasera (Mitad Inferior)**")
            r3, r4 = st.columns(2)
            if r3.button("🔄 Girar 90°", key="btn_r_90"):
                st.session_state.rot_reverso = (st.session_state.rot_reverso + 90) % 360
            if r4.button("🙃 Voltear 180°", key="btn_r_180"):
                st.session_state.rot_reverso = (st.session_state.rot_reverso + 180) % 360
                
            img_reverso_final = img_reverso_base.rotate(360 - st.session_state.rot_reverso, expand=True)
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
                img.convert("RGB").save(buffer_temp, format="JPEG", quality=85)
                buffer_temp.seek(0)
                
                c.drawImage(ImageReader(buffer_temp), pos_x, pos_y, width=nuevo_ancho, height=nuevo_alto)

            # Renderizar frente y reverso en PDF
            agregar_imagen(img_frente_final, alto_pagina * 0.75)
            agregar_imagen(img_reverso_final, alto_pagina * 0.25)
            
            c.save()
            pdf_buffer.seek(0)

            st.success("¡PDF generado!")
            st.download_button(
                label="📥 Descargar PDF",
                data=pdf_buffer,
                file_name="cedula_completa.pdf",
                mime="application/pdf",
                use_container_width=True
            )
    else:
        st.info("👈 Suba los dos archivos en el panel derecho para visualizar la cédula.")
