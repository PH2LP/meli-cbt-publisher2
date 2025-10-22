#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
category_downloader.py — v5 (CBT version)
Descarga el árbol de categorías Global Selling (CBT)
y lo guarda en data/cbt_categories.json con todos los atributos incluidos.
"""

import os, sys, gzip, json, requests
from dotenv import load_dotenv

# ============================================================
# 🧩 Auto-activar entorno virtual si existe
# ============================================================
venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")
if os.path.exists(venv_python) and sys.executable != venv_python:
    print(f"⚙️ Activando entorno virtual automáticamente desde: {venv_python}")
    os.execv(venv_python, [venv_python] + sys.argv)

# ============================================================
# 🚀 Cargar entorno y credenciales
# ============================================================
load_dotenv()
ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "")
API_URL = "https://api.mercadolibre.com/sites/CBT/categories/all?withAttributes=true"
OUT_DIR = "data"
OUT_GZ = os.path.join(OUT_DIR, "cbt_categories.gz")
OUT_JSON = os.path.join(OUT_DIR, "cbt_categories.json")

os.makedirs(OUT_DIR, exist_ok=True)

if not ACCESS_TOKEN:
    print("❌ ERROR: No se encontró ML_ACCESS_TOKEN en .env o variables de entorno.")
    print("➡️ Usa: export ML_ACCESS_TOKEN='APP_USR-XXXXXX'")
    sys.exit(1)

print("⬇️ Descargando árbol de categorías Global Selling (CBT)...")
print(f"🔑 Token usado: {ACCESS_TOKEN[:20]}...")

try:
    r = requests.get(API_URL, headers={"Authorization": f"Bearer {ACCESS_TOKEN}"}, stream=True)
    print(f"🔍 HTTP status: {r.status_code}")
    r.raise_for_status()
except Exception as e:
    print(f"❌ Error al descargar: {e}")
    sys.exit(1)

with open(OUT_GZ, "wb") as f:
    for chunk in r.iter_content(chunk_size=8192):
        f.write(chunk)

print(f"✅ Archivo comprimido guardado: {OUT_GZ}")

print("🗜️ Descomprimiendo JSON...")
try:
    with gzip.open(OUT_GZ, "rb") as gz_file:
        data = json.loads(gz_file.read().decode("utf-8"))
except Exception as e:
    print(f"❌ Error al descomprimir: {e}")
    sys.exit(1)

with open(OUT_JSON, "w", encoding="utf-8") as out:
    json.dump(data, out, indent=2, ensure_ascii=False)

print(f"✅ Árbol de categorías guardado: {OUT_JSON}")
print(f"📊 Total de categorías descargadas: {len(data)}")

print("\n🎯 Finalizado correctamente.")