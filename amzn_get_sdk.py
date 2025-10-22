#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
amzn_get_sdk.py
Descarga datos de productos desde Amazon SP-API y los guarda en formato JSON.
Compatible con entorno virtual automático y variables del archivo .env
"""
# === AUTO-ACTIVADOR DEL ENTORNO VIRTUAL ===
import os, sys

if sys.prefix == sys.base_prefix:  # Detecta si NO estás dentro del entorno virtual
    # Detecta la carpeta base del proyecto aunque corras desde fuera
    current_file = os.path.abspath(__file__)
    base_dir = os.path.dirname(current_file)

    # Recorre hacia arriba hasta encontrar una carpeta que contenga "venv/bin/python"
    search_dir = base_dir
    venv_python = None
    for _ in range(4):  # sube hasta 4 niveles (por si estás en subcarpetas)
        candidate = os.path.join(search_dir, "venv", "bin", "python")
        if os.path.exists(candidate):
            venv_python = candidate
            break
        search_dir = os.path.dirname(search_dir)

    if venv_python:
        print(f"⚙️ Activando entorno virtual automáticamente desde: {venv_python}")
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        print("⚠️ No se encontró el entorno virtual (venv). Créalo con: python3.11 -m venv venv")
        sys.exit(1)

import os
import sys
import json
import time
from dotenv import load_dotenv
from sp_api.api import CatalogItems
from sp_api.base import Marketplaces, SellingApiException

# === CONFIGURACIÓN ===
load_dotenv()
print("✅ Variables de entorno cargadas correctamente.")

OUTPUT_DIR = "outputs/json"
ASINS_FILE = "asins.txt"

os.makedirs(OUTPUT_DIR, exist_ok=True)

# === FUNCIÓN PRINCIPAL ===
def main():
    print("📦 Iniciando extracción con Amazon SP-API (SDK oficial)...\n")

    if not os.path.exists(ASINS_FILE):
        print("⚠️ No se encontró asins.txt — créalo con un ASIN por línea.")
        return

    # Carga los ASINs desde el archivo
    with open(ASINS_FILE, "r", encoding="utf-8") as f:
        asins = [a.strip() for a in f if a.strip()]

    if not asins:
        print("⚠️ No hay ASINs en el archivo.")
        return

    # Inicializa cliente de Amazon SP-API
    client = CatalogItems(
        marketplace=Marketplaces.US,
        credentials={
            "refresh_token": os.getenv("REFRESH_TOKEN"),
            "lwa_app_id": os.getenv("LWA_CLIENT_ID"),
            "lwa_client_secret": os.getenv("LWA_CLIENT_SECRET"),
            "aws_access_key": os.getenv("AWS_ACCESS_KEY_ID"),
            "aws_secret_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
        },
    )

    successes, failures = 0, 0

    for asin in asins:
        print(f"🔍 Consultando ASIN {asin}...")
        try:
            res = client.get_catalog_item(asin, includedData=["attributes", "summaries", "images"])
            data = res.payload

            save_path = os.path.join(OUTPUT_DIR, f"{asin}.json")
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"✅ Guardado: {save_path}")

            successes += 1

        except SellingApiException as e:
            print(f"❌ Error con ASIN {asin}: {e}")
            failures += 1

        time.sleep(1.2)  # pausa entre requests

    print("\n📊 Resumen:")
    print(f"✅ Éxitos: {successes}")
    print(f"❌ Fallos: {failures}")
    print(f"📁 Archivos en: {os.path.abspath(OUTPUT_DIR)}")

# === EJECUCIÓN ===
if __name__ == "__main__":
    main()