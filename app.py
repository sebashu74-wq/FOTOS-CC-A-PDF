import hashlib
import io
import math
import re

import cv2
import numpy as np
import streamlit as st
import zxingcpp
from PIL import Image, ImageOps
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

st.set_page_config(page_title="Unificador Cédulas Colombia", page_icon="📄", layout="wide")
st.title("📄 Unificador de Cédula a PDF")

TAM_PDF = 1100               # tamaño máximo (px) de las imágenes que van al PDF
TAMS_ESCANEO = (1600, 3000)  # primero rápido; si no lee el código, reintenta con más resolución
IGNORAR = {"DSK", "PUB", "PUBDSK"}


# ---------------------------------------------------------------- imágenes
def abrir_imagen(datos: bytes, max_dim: int) -> Image.Image:
    """Abre la imagen decodificándola ya reducida (mucho más rápido en fotos de celular)."""
    img = Image.open(io.BytesIO(datos))
    img.draft("RGB", (max_dim, max_dim))  # solo afecta a JPEG
    img = ImageOps.exif_transpose(img)
    if img.mode in ("RGBA", "LA", "P"):
        img = img.convert("RGBA")
        fondo = Image.new("RGB", img.size, "white")
        fondo.paste(img, mask=img.getchannel("A"))
        img = fondo
    else:
        img = img.convert("RGB")
    if max(img.size) > max_dim:
        img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)
    return img


# ------------------------------------------------------- código PDF417 (reverso)
def leer_pdf417(img: Image.Image):
    """
    Lee el PDF417 UNA sola vez (zxing ya prueba las rotaciones internamente) y
    calcula cuántos grados hay que girar la imagen para dejarla derecha.
    Retorna (rotacion_grados, bytes_crudos) o None.
    """
    gris = np.asarray(img.convert("L"))
    resultados = zxingcpp.read_barcodes(
        gris,
        formats=zxingcpp.BarcodeFormat.PDF417,
        try_rotate=True,
        try_invert=False,
    )
    for r in resultados:
        p = r.position
        # Dirección de lectura del símbolo (esquina sup-izq -> sup-der) en coordenadas de imagen
        ang = math.degrees(math.atan2(p.top_right.y - p.top_left.y,
                                      p.top_right.x - p.top_left.x))
        rot = (int(round(ang / 90.0)) * 90) % 360
        return rot, bytes(r.bytes)
    return None


def extraer_nombre(raw: bytes) -> str:
    """Extrae 'APELLIDOS NOMBRES' (mismo orden que la cédula). Devuelve '' si no es confiable."""
    texto = raw.decode("latin-1")

    # 1) Formato estándar: campos de 23 caracteres en posiciones fijas
    if len(texto) >= 150:
        campos = [texto[a:b] for a, b in ((58, 81), (81, 104), (104, 127), (127, 150))]
        vacio = lambda c: not c.strip("\x00 ")
        if (all(re.fullmatch(r"[A-ZÑ \x00]*", c) for c in campos)
                and not vacio(campos[0]) and not vacio(campos[2])):
            partes = [" ".join(c.replace("\x00", " ").split()) for c in campos if not vacio(c)]
            return " ".join(partes)

    # 2) Respaldo: palabras en mayúsculas dentro del texto
    limpio = texto.replace("\x00", " ")
    palabras = re.findall(r"(?<![A-Za-z])[A-ZÑ]{2,}(?![A-Za-z])", limpio)
    palabras = [w for w in palabras if w not in IGNORAR]
    if len(palabras) >= 2 and sum(len(w) for w in palabras[:4]) >= 6:
        return " ".join(palabras[:4])
    return ""


# --------------------------------------------------------- frente (por rostro)
@st.cache_resource
def cargar_detector():
    return cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def orientar_frente(img: Image.Image, rot_ref: int):
    """Prueba los 4 giros en miniatura y elige el que muestra el rostro derecho."""
    detector = cargar_detector()
    mini = img.copy()
    mini.thumbnail((640, 640))
    mejor_ang, mejor_puntaje = None, 0
    for ang in (0, 90, 180, 270):
        m = mini.rotate(ang, expand=True) if ang else mini
        gris = cv2.equalizeHist(np.asarray(m.convert("L")))
        caras = detector.detectMultiScale(gris, scaleFactor=1.1, minNeighbors=5, minSize=(20, 20))
        puntaje = sum(int(w) * int(h) for (_, _, w, h) in caras)
        if puntaje > mejor_puntaje:
            mejor_ang, mejor_puntaje = ang, puntaje
    if mejor_ang is not None:
        return (img.rotate(mejor_ang, expand=True) if mejor_ang else img), True

    # Respaldo: asumir que se fotografió con la misma orientación que el reverso
    fr = img.rotate(rot_ref, expand=True) if rot_ref else img
    if fr.height > fr.width:
        fr = fr.rotate(90, expand=True)
    return fr, False


# ------------------------------------------------------------- procesamiento
@st.cache_data(show_spinner=False, max_entries=3, ttl=600)
def analizar(datos_a: bytes, datos_b: bytes):
    """Clasifica frente/reverso, orienta ambos y extrae el nombre. Se cachea por contenido."""
    datos = (datos_a, datos_b)
    idx_rev, hit, imgs = None, None, None

    for tam in TAMS_ESCANEO:
        imgs = [abrir_imagen(d, tam) for d in datos]
        for i, img in enumerate(imgs):
            hit = leer_pdf417(img)
            if hit:
                idx_rev = i
                break
        if idx_rev is not None:
            break

    if idx_rev is None:
        idx_rev = 1  # sin código: se asume que la segunda es el reverso
    img_rev, img_fre = imgs[idx_rev], imgs[1 - idx_rev]

    rot, nombre = 0, ""
    if hit:
        rot, raw = hit
        if rot:
            img_rev = img_rev.rotate(rot, expand=True)
        nombre = extraer_nombre(raw)

    img_fre, cara_ok = orientar_frente(img_fre, rot)

    for im in (img_fre, img_rev):
        im.thumbnail((TAM_PDF, TAM_PDF), Image.Resampling.LANCZOS)

    return img_fre, img_rev, nombre, hit is not None, cara_ok


def crear_pdf(img_frente: Image.Image, img_reverso: Image.Image) -> io.BytesIO:
    pdf = io.BytesIO()
    c = canvas.Canvas(pdf, pagesize=letter)
    ancho_pag, alto_pag = letter
    ancho_max, alto_max = 350, 220

    def agregar(img, centro_y):
        ratio = min(ancho_max / img.width, alto_max / img.height)
        w, h = int(img.width * ratio), int(img.height * ratio)
        buf = io.BytesIO()
        img.convert("RGB").save(buf, format="JPEG", quality=80)
        buf.seek(0)
        c.drawImage(ImageReader(buf), (ancho_pag - w) / 2, centro_y - h / 2, width=w, height=h)

    agregar(img_frente, alto_pag * 0.75)
    agregar(img_reverso, alto_pag * 0.25)
    c.save()
    pdf.seek(0)
    return pdf


# ------------------------------------------------------------------- interfaz
for k in ("rot_frente", "rot_reverso"):
    st.session_state.setdefault(k, 0)


def girar(clave: str, grados: int):
    st.session_state[clave] = (st.session_state[clave] + grados) % 360


col_izq, col_der = st.columns([2, 1])
pareja = None

with col_der:
    st.subheader("📤 Cargar Imágenes")
    modo = st.radio("Método de carga:", ["Arrastrar las 2 fotos juntas", "Subir por separado"])

    if modo == "Arrastrar las 2 fotos juntas":
        archivos = st.file_uploader(
            "Selecciona o arrastra las 2 imágenes aquí",
            type=["jpg", "jpeg", "png"],
            accept_multiple_files=True,
        )
        if archivos:
            if len(archivos) == 2:
                pareja = archivos
            else:
                st.warning("Selecciona exactamente 2 imágenes.")
    else:
        f_file = st.file_uploader("1. Cédula Frente", type=["jpg", "jpeg", "png"])
        r_file = st.file_uploader("2. Cédula Trasera", type=["jpg", "jpeg", "png"])
        if f_file and r_file:
            pareja = [f_file, r_file]

    resultado = None
    if pareja:
        b1, b2 = pareja[0].getvalue(), pareja[1].getvalue()
        firma = hashlib.md5(b1 + b2).hexdigest()

        if st.session_state.get("firma") != firma:  # fotos nuevas -> reiniciar giros
            st.session_state.firma = firma
            st.session_state.rot_frente = 0
            st.session_state.rot_reverso = 0

        with st.spinner("Procesando..."):
            resultado = analizar(b1, b2)

        img_frente, img_reverso, nombre, codigo_ok, cara_ok = resultado

        sugerido = f"CC {nombre}" if nombre else "CC"
        sugerido = re.sub(r'[\\/:*?"<>|]', "", sugerido).strip()
        nombre_final = st.text_input("Nombre del archivo", value=sugerido, key=f"nombre_{firma}")
        nombre_pdf = re.sub(r'[\\/:*?"<>|]', "", nombre_final).strip() or "CC"
        if not nombre_pdf.lower().endswith(".pdf"):
            nombre_pdf += ".pdf"

with col_izq:
    if resultado:
        st.subheader("👁️ Vista Previa")

        if not codigo_ok:
            st.warning("No pude leer el código de barras del reverso: revisa su orientación y el nombre.")
        elif not nombre:
            st.info("El código se leyó, pero no pude extraer el nombre: el archivo se llamará solo 'CC'.")
        if not cara_ok:
            st.warning("No pude detectar el rostro en el frente: revisa su orientación.")

        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**1. Frente (Mitad Superior)**")
            b_a, b_b = st.columns(2)
            b_a.button("🔄 Girar 90°", key="f_90", on_click=girar, args=("rot_frente", 90))
            b_b.button("🙃 Voltear 180°", key="f_180", on_click=girar, args=("rot_frente", 180))
            frente_render = img_frente.rotate(-st.session_state.rot_frente, expand=True)
            st.image(frente_render, width="stretch")

        with c2:
            st.markdown("**2. Trasera (Mitad Inferior)**")
            b_c, b_d = st.columns(2)
            b_c.button("🔄 Girar 90°", key="r_90", on_click=girar, args=("rot_reverso", 90))
            b_d.button("🙃 Voltear 180°", key="r_180", on_click=girar, args=("rot_reverso", 180))
            reverso_render = img_reverso.rotate(-st.session_state.rot_reverso, expand=True)
            st.image(reverso_render, width="stretch")

        st.markdown("---")
        st.download_button(
            label=f"📥 Descargar {nombre_pdf}",
            data=crear_pdf(frente_render, reverso_render),
            file_name=nombre_pdf,
            mime="application/pdf",
            type="primary",
            width="stretch",
        )
    else:
        st.info("👈 Utiliza el panel de la derecha para arrastrar o subir las 2 imágenes de la cédula.")
