"""
Procesador Unificado de Publicaciones (Facebook e Instagram) para Nexus FI (UAEMéx)
----------------------------------------------------------------------------------
Procesa archivos JSON descargados desde Apify (Facebook Posts Scraper / Instagram Post Scraper).
Almacena la información en SQLite (nexus_fi.db), descarga imágenes/portadas en 'imagenes/'
y aplica OCR en español con Tesseract.

Soporte:
- Facebook: postId, time, text, likes, shares, media (Photo/Video), sharedPost.
- Instagram: id, timestamp, caption, likesCount, displayUrl (Image/Video/Sidecar).

Reglas:
- No almacena comentarios ni datos personales de usuarios.
- Idempotencia total: no repite descargas ni reejecuta OCR innecesariamente.
- Actualiza informe_proceso.md con métricas detalladas.
"""

import os
import sys
import json
import sqlite3
import shutil
from datetime import datetime
from pathlib import Path
import requests
from PIL import Image
import pytesseract

# Configuración de rutas
BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "nexus_fi.db"
IMAGES_DIR = BASE_DIR / "imagenes"
REPORT_PATH = BASE_DIR / "informe_proceso.md"


def configurar_tesseract():
    """Detecta y configura la ruta del binario de Tesseract en Windows."""
    if shutil.which("tesseract"):
        pytesseract.pytesseract.tesseract_cmd = shutil.which("tesseract")
    elif os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe"):
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    elif os.path.exists(r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"):
        pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe"
    else:
        print("[AVISO] No se detectó tesseract en la ruta estándar. Asegúrate de que esté en PATH.")


def inicializar_bd(db_path: Path):
    """Crea o actualiza las tablas en SQLite garantizando compatibilidad."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Tabla publicaciones
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS publicaciones (
        postId TEXT PRIMARY KEY,
        url TEXT,
        fecha TEXT,
        texto TEXT,
        likes INTEGER DEFAULT 0,
        shares INTEGER DEFAULT 0,
        es_video INTEGER DEFAULT 0,
        es_compartida INTEGER DEFAULT 0,
        texto_compartido TEXT,
        pagina_origen TEXT,
        red_social TEXT DEFAULT 'facebook'
    );
    """)

    # Migración de columnas si la BD ya existía previamente
    cursor.execute("PRAGMA table_info(publicaciones);")
    cols_pub = [col[1] for col in cursor.fetchall()]
    if "red_social" not in cols_pub:
        cursor.execute("ALTER TABLE publicaciones ADD COLUMN red_social TEXT DEFAULT 'facebook';")

    # Tabla imágenes
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS imagenes (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        postId TEXT NOT NULL,
        numero_imagen INTEGER NOT NULL,
        nombre_archivo TEXT NOT NULL,
        ruta_archivo TEXT NOT NULL,
        url_origen TEXT,
        texto_ocr TEXT,
        estado_descarga TEXT,
        error_mensaje TEXT,
        es_portada_video INTEGER DEFAULT 0,
        es_de_compartida INTEGER DEFAULT 0,
        es_sidecar INTEGER DEFAULT 0,
        FOREIGN KEY (postId) REFERENCES publicaciones(postId),
        UNIQUE(postId, numero_imagen)
    );
    """)

    cursor.execute("PRAGMA table_info(imagenes);")
    cols_img = [col[1] for col in cursor.fetchall()]
    if "es_sidecar" not in cols_img:
        cursor.execute("ALTER TABLE imagenes ADD COLUMN es_sidecar INTEGER DEFAULT 0;")

    conn.commit()
    conn.close()


def descargar_imagen(url: str, destino: Path, session: requests.Session) -> tuple[bool, str]:
    """Descarga de imagen con política de no re-descarga si ya existe."""
    if destino.exists() and destino.stat().st_size > 0:
        return True, "ya_existia"

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        resp = session.get(url, headers=headers, timeout=25)
        resp.raise_for_status()

        destino.parent.mkdir(parents=True, exist_ok=True)
        with open(destino, "wb") as f:
            f.write(resp.content)
        return True, "descargado"
    except Exception as e:
        return False, str(e)


def aplicar_ocr_espanol(ruta_imagen: Path) -> tuple[str, str]:
    """Ejecuta Tesseract OCR en español sobre la imagen indicada."""
    try:
        with Image.open(ruta_imagen) as img:
            if img.mode not in ("RGB", "L"):
                img = img.convert("RGB")
            texto = pytesseract.image_to_string(img, lang="spa")
            return texto.strip(), ""
    except Exception as e:
        return "", str(e)


def detectar_plataforma(post: dict) -> str:
    """Identifica si el registro corresponde a Facebook o a Instagram."""
    if "postId" in post:
        return "facebook"
    if "id" in post and ("caption" in post or "displayUrl" in post or "shortCode" in post):
        return "instagram"
    # Detección por claves secundarias
    if "displayUrl" in post or "caption" in post:
        return "instagram"
    return "facebook"


def normalizar_post(post: dict, plataforma: str) -> dict:
    """Extrae y normaliza los datos comunes de la publicación según la plataforma."""
    if plataforma == "instagram":
        post_id = str(post.get("id") or "").strip()
        url = post.get("url") or post.get("inputUrl") or ""
        if not url and post.get("shortCode"):
            url = f"https://www.instagram.com/p/{post['shortCode']}/"

        fecha = post.get("timestamp") or ""
        texto = post.get("caption") or ""
        likes = post.get("likesCount") or 0
        shares = 0  # Instagram no incluye shares en este scraper

        tipo = str(post.get("type") or "").strip().lower()
        is_video = 1 if tipo == "video" else 0
        is_sidecar = 1 if tipo == "sidecar" else 0

        # Para Instagram, la página de origen es el usuario que publicó
        owner = post.get("ownerUsername") or post.get("ownerFullName") or ""

        # Recolección de imagen: displayUrl es portada si es video o carrusel (Sidecar), o foto regular
        imagenes = []
        display_url = post.get("displayUrl")
        if display_url:
            imagenes.append({
                "url": display_url,
                "es_portada": 1 if is_video else 0,
                "es_compartida": 0,
                "es_sidecar": is_sidecar
            })

        return {
            "postId": post_id,
            "url": url,
            "fecha": fecha,
            "texto": texto,
            "likes": likes,
            "shares": shares,
            "es_video": is_video,
            "es_compartida": 0,
            "texto_compartido": "",
            "pagina_origen": owner,
            "red_social": "instagram",
            "es_sidecar": is_sidecar,
            "imagenes": imagenes,
            "tipo_original": tipo.capitalize() if tipo else "Image"
        }

    else:
        # Facebook
        post_id = str(post.get("postId") or "").strip()
        url = post.get("url") or post.get("topLevelUrl") or ""
        fecha = post.get("time") or ""
        texto = post.get("text") or ""
        likes = post.get("likesCount") or post.get("likes") or 0
        shares = post.get("shares") or 0
        is_video = bool(post.get("isVideo", False))

        shared_post = post.get("sharedPost")
        es_compartida = 1 if (shared_post and isinstance(shared_post, dict)) else 0
        texto_compartido = ""
        pagina_origen = ""

        if es_compartida:
            texto_compartido = shared_post.get("text") or ""
            page_name_data = shared_post.get("pageName")
            if isinstance(page_name_data, dict):
                pagina_origen = page_name_data.get("name") or ""
            elif isinstance(page_name_data, str):
                pagina_origen = page_name_data
            else:
                user_data = shared_post.get("user")
                if isinstance(user_data, dict):
                    pagina_origen = user_data.get("name") or ""

        media_list = post.get("media") or []
        for m in media_list:
            if isinstance(m, dict) and m.get("__typename") == "Video":
                is_video = True
                break

        imagenes = []
        if is_video:
            cover_url = None
            for m in media_list:
                if isinstance(m, dict):
                    cover_url = (
                        m.get("thumbnail") or
                        (m.get("thumbnailImage") or {}).get("uri") or
                        ((m.get("preferred_thumbnail") or {}).get("image") or {}).get("uri") or
                        (m.get("image") or {}).get("uri")
                    )
                    if cover_url:
                        break
            if not cover_url:
                cover_url = post.get("thumbnail")
            if cover_url:
                imagenes.append({
                    "url": cover_url,
                    "es_portada": 1,
                    "es_compartida": 0,
                    "es_sidecar": 0
                })
        else:
            for m in media_list:
                if isinstance(m, dict) and m.get("__typename") == "Photo":
                    img_uri = (m.get("image") or {}).get("uri") or m.get("thumbnail")
                    if img_uri:
                        imagenes.append({
                            "url": img_uri,
                            "es_portada": 0,
                            "es_compartida": 0,
                            "es_sidecar": 0
                        })

            if es_compartida and shared_post:
                shared_media = shared_post.get("media") or []
                for sm in shared_media:
                    if isinstance(sm, dict) and sm.get("__typename") == "Photo":
                        img_uri = (sm.get("image") or {}).get("uri") or sm.get("thumbnail")
                        if img_uri:
                            imagenes.append({
                                "url": img_uri,
                                "es_portada": 0,
                                "es_compartida": 1,
                                "es_sidecar": 0
                            })

        return {
            "postId": post_id,
            "url": url,
            "fecha": fecha,
            "texto": texto,
            "likes": likes,
            "shares": shares,
            "es_video": 1 if is_video else 0,
            "es_compartida": es_compartida,
            "texto_compartido": texto_compartido,
            "pagina_origen": pagina_origen,
            "red_social": "facebook",
            "imagenes": imagenes,
            "tipo_original": "Video" if is_video else ("Compartida" if es_compartida else "Foto/Post")
        }


def procesar_archivo_json(json_path: Path, conn: sqlite3.Connection, session: requests.Session) -> dict:
    """Procesa un archivo JSON específico de Facebook o Instagram."""
    cursor = conn.cursor()
    print(f"\n[INFO] Procesando archivo: {json_path.name}")

    with open(json_path, "r", encoding="utf-8") as f:
        posts_raw = json.load(f)

    resumen = {
        "archivo": json_path.name,
        "total_posts": len(posts_raw),
        "posts_procesados": 0,
        "por_red": {"facebook": 0, "instagram": 0},
        "por_tipo": {"video": 0, "compartida": 0, "sidecar": 0, "regular": 0},
        "imagenes_procesadas": 0,
        "imagenes_nuevas": 0,
        "imagenes_reutilizadas": 0,
        "textos_ocr_leidos": 0,
        "errores_descarga": [],
        "errores_ocr": [],
        "detalles": []
    }

    for raw_post in posts_raw:
        plataforma = detectar_plataforma(raw_post)
        item = normalizar_post(raw_post, plataforma)
        post_id = item["postId"]
        if not post_id:
            continue

        resumen["por_red"][item["red_social"]] += 1
        if item["es_video"]:
            resumen["por_tipo"]["video"] += 1
        elif item.get("es_sidecar"):
            resumen["por_tipo"]["sidecar"] += 1
        elif item["es_compartida"]:
            resumen["por_tipo"]["compartida"] += 1
        else:
            resumen["por_tipo"]["regular"] += 1

        # Guardar / actualizar en tabla 'publicaciones'
        cursor.execute("""
        INSERT INTO publicaciones (
            postId, url, fecha, texto, likes, shares, es_video, es_compartida,
            texto_compartido, pagina_origen, red_social
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(postId) DO UPDATE SET
            url=excluded.url,
            fecha=excluded.fecha,
            texto=excluded.texto,
            likes=excluded.likes,
            shares=excluded.shares,
            es_video=excluded.es_video,
            es_compartida=excluded.es_compartida,
            texto_compartido=excluded.texto_compartido,
            pagina_origen=excluded.pagina_origen,
            red_social=excluded.red_social;
        """, (
            item["postId"], item["url"], item["fecha"], item["texto"],
            item["likes"], item["shares"], item["es_video"], item["es_compartida"],
            item["texto_compartido"], item["pagina_origen"], item["red_social"]
        ))
        conn.commit()
        resumen["posts_procesados"] += 1

        # Procesar imágenes asociadas
        imagenes_detalle = []
        for idx, img_info in enumerate(item["imagenes"], start=1):
            resumen["imagenes_procesadas"] += 1
            img_url = img_info["url"]
            file_name = f"{post_id}_{idx}.jpg"
            file_path = IMAGES_DIR / file_name

            # Consultar si ya fue procesada en la BD
            cursor.execute("SELECT texto_ocr, estado_descarga FROM imagenes WHERE postId = ? AND numero_imagen = ?", (post_id, idx))
            registro_previo = cursor.fetchone()

            estado_descarga = "completado"
            error_descarga = ""
            texto_ocr = ""

            exito, motivo = descargar_imagen(img_url, file_path, session)
            if not exito:
                estado_descarga = "error"
                error_descarga = motivo
                resumen["errores_descarga"].append({
                    "postId": post_id,
                    "archivo": file_name,
                    "url": img_url,
                    "error": motivo
                })
                print(f"  [ERROR DESCARGA] {file_name}: {motivo}")
            else:
                if motivo == "ya_existia":
                    resumen["imagenes_reutilizadas"] += 1
                else:
                    resumen["imagenes_nuevas"] += 1

                # Reutilizar OCR previo si está disponible
                if registro_previo and registro_previo[0] is not None and registro_previo[1] == "completado":
                    texto_ocr = registro_previo[0]
                else:
                    texto_ocr, err_ocr = aplicar_ocr_espanol(file_path)
                    if err_ocr:
                        resumen["errores_ocr"].append({
                            "postId": post_id,
                            "archivo": file_name,
                            "error": err_ocr
                        })
                        print(f"  [ERROR OCR] {file_name}: {err_ocr}")

                if texto_ocr and len(texto_ocr.strip()) > 0:
                    resumen["textos_ocr_leidos"] += 1

            # Guardar en SQLite
            cursor.execute("""
            INSERT INTO imagenes (
                postId, numero_imagen, nombre_archivo, ruta_archivo, url_origen,
                texto_ocr, estado_descarga, error_mensaje, es_portada_video, es_de_compartida, es_sidecar
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(postId, numero_imagen) DO UPDATE SET
                nombre_archivo=excluded.nombre_archivo,
                ruta_archivo=excluded.ruta_archivo,
                url_origen=excluded.url_origen,
                texto_ocr=excluded.texto_ocr,
                estado_descarga=excluded.estado_descarga,
                error_mensaje=excluded.error_mensaje,
                es_portada_video=excluded.es_portada_video,
                es_de_compartida=excluded.es_de_compartida,
                es_sidecar=excluded.es_sidecar;
            """, (
                post_id, idx, file_name, str(file_path), img_url,
                texto_ocr, estado_descarga, error_descarga,
                img_info["es_portada"], img_info["es_compartida"], img_info.get("es_sidecar", 0)
            ))
            conn.commit()

            imagenes_detalle.append({
                "archivo": file_name,
                "es_portada": bool(img_info["es_portada"]),
                "es_sidecar": bool(img_info.get("es_sidecar", 0)),
                "ocr_leido": bool(texto_ocr and len(texto_ocr.strip()) > 0),
                "longitud_texto": len(texto_ocr.strip()) if texto_ocr else 0,
                "muestra_ocr": (texto_ocr.strip()[:100] + "...") if (texto_ocr and len(texto_ocr.strip()) > 100) else (texto_ocr.strip() if texto_ocr else "")
            })

        resumen["detalles"].append({
            "postId": post_id,
            "red_social": item["red_social"],
            "url": item["url"],
            "fecha": item["fecha"],
            "likes": item["likes"],
            "shares": item["shares"],
            "tipo_original": item["tipo_original"],
            "pagina_origen": item["pagina_origen"],
            "imagenes": imagenes_detalle
        })

    return resumen


def generar_informe_consolidado(resumenes: list[dict]):
    """Genera el informe Markdown actualizado con estadísticas consolidadas."""
    md = []
    md.append("# Informe de Procesamiento de Publicaciones - Proyecto Nexus FI (UAEMéx)\n")
    md.append(f"**Fecha de generación:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

    total_posts = sum(r["posts_procesados"] for r in resumenes)
    total_imgs = sum(r["imagenes_procesadas"] for r in resumenes)
    total_ocr = sum(r["textos_ocr_leidos"] for r in resumenes)
    total_err_desc = sum(len(r["errores_descarga"]) for r in resumenes)
    total_err_ocr = sum(len(r["errores_ocr"]) for r in resumenes)

    fb_posts = sum(r["por_red"]["facebook"] for r in resumenes)
    ig_posts = sum(r["por_red"]["instagram"] for r in resumenes)

    md.append("## 1. Resumen General Consolidado\n")
    md.append(f"- **Total de publicaciones procesadas:** {total_posts}")
    md.append(f"  - **Facebook:** {fb_posts}")
    md.append(f"  - **Instagram:** {ig_posts}")
    md.append(f"- **Total de imágenes procesadas (fotos y portadas):** {total_imgs}")
    md.append(f"- **Imágenes donde OCR extrajo texto:** {total_ocr}")
    md.append(f"- **Errores de descarga:** {total_err_desc}")
    md.append(f"- **Errores de OCR:** {total_err_ocr}\n")

    md.append("## 2. Métricas por Archivo Procesado\n")
    for r in resumenes:
        md.append(f"### Archivo: `{r['archivo']}`")
        md.append(f"- **Publicaciones:** {r['posts_procesados']} (Facebook: {r['por_red']['facebook']}, Instagram: {r['por_red']['instagram']})")
        md.append(f"- **Tipos:** Videos: {r['por_tipo']['video']}, Carruseles/Sidecar: {r['por_tipo']['sidecar']}, Compartidas: {r['por_tipo']['compartida']}, Regulares: {r['por_tipo']['regular']}")
        md.append(f"- **Imágenes:** {r['imagenes_procesadas']} ({r['imagenes_nuevas']} nuevas descargadas, {r['imagenes_reutilizadas']} reutilizadas)")
        md.append(f"- **Textos OCR leídos:** {r['textos_ocr_leidos']}\n")

    md.append("## 3. Detalle de Publicaciones")
    for r in resumenes:
        md.append(f"\n#### Archivo: `{r['archivo']}`\n")
        for d in r["detalles"]:
            badge_red = f"[{d['red_social'].upper()}]"
            md.append(f"##### {badge_red} Post ID: `{d['postId']}`")
            md.append(f"- **URL:** {d['url']}")
            md.append(f"- **Fecha:** {d['fecha']}")
            md.append(f"- **Interacciones:** {d['likes']} likes, {d['shares']} shares")
            md.append(f"- **Tipo:** {d['tipo_original']}")
            if d['pagina_origen']:
                md.append(f"- **Origen / Autor:** {d['pagina_origen']}")
            md.append(f"- **Imágenes procesadas:** {len(d['imagenes'])}")
            for img in d['imagenes']:
                estado_txt = "Texto detectado" if img['ocr_leido'] else "Sin texto detectado"
                tags = []
                if img['es_portada']:
                    tags.append("Portada de video")
                if img['es_sidecar']:
                    tags.append("Portada de carrusel/Sidecar")
                tag_str = f" ({', '.join(tags)})" if tags else ""
                md.append(f"  - `{img['archivo']}`{tag_str}: **{estado_txt}** ({img['longitud_texto']} caracteres)")
                if img['muestra_ocr']:
                    muestra_limpia = img['muestra_ocr'].replace('\n', ' ')
                    md.append(f"    - *Muestra OCR:* \"{muestra_limpia}\"")
            md.append("")

    md.append("## 4. Registro de Incidencias y Errores")
    if total_err_desc == 0 and total_err_ocr == 0:
        md.append("- **No se presentaron errores:** Todas las imágenes y portadas fueron procesadas e indexadas exitosamente sin interrupciones.")
    else:
        for r in resumenes:
            if r["errores_descarga"]:
                md.append(f"### Errores de descarga en `{r['archivo']}`:")
                for e in r["errores_descarga"]:
                    md.append(f"- Post `{e['postId']}` | Archivo `{e['archivo']}`: {e['error']}")
            if r["errores_ocr"]:
                md.append(f"### Errores de OCR en `{r['archivo']}`:")
                for e in r["errores_ocr"]:
                    md.append(f"- Post `{e['postId']}` | Archivo `{e['archivo']}`: {e['error']}")

    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(md))


def main():
    configurar_tesseract()
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    inicializar_bd(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    session = requests.Session()

    archivos_a_procesar = []

    # Si se pasa un archivo como argumento en línea de comandos: py procesar_posts.py <archivo.json>
    if len(sys.argv) > 1:
        ruta_arg = Path(sys.argv[1])
        if not ruta_arg.is_absolute():
            ruta_arg = BASE_DIR / ruta_arg
        if ruta_arg.exists():
            archivos_a_procesar.append(ruta_arg)
        else:
            print(f"[ERROR] El archivo especificado no existe: {ruta_arg}")
            sys.exit(1)
    else:
        # Por defecto busca los archivos dataset_*.json en el directorio
        archivos_a_procesar = sorted(list(BASE_DIR.glob("dataset_*.json")))
        if not archivos_a_procesar:
            archivos_a_procesar = sorted(list(BASE_DIR.glob("*.json")))

    if not archivos_a_procesar:
        print(f"[ERROR] No se encontraron archivos JSON para procesar en {BASE_DIR}")
        sys.exit(1)

    print(f"[INFO] Archivos identificados para procesar ({len(archivos_a_procesar)}):")
    for a in archivos_a_procesar:
        print(f" - {a.name}")

    resumenes = []
    for arch in archivos_a_procesar:
        res = procesar_archivo_json(arch, conn, session)
        resumenes.append(res)

    conn.close()

    generar_informe_consolidado(resumenes)
    print("\n[PROCESAMIENTO GLOBAL COMPLETADO CON ÉXITO]")
    print(f"Informe actualizado en: {REPORT_PATH}")


if __name__ == "__main__":
    main()
