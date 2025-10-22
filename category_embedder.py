#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
category_embedder.py
Convierte el árbol de categorías CBT en embeddings locales para clasificación IA.
"""

import os, sys, json, numpy as np, time
from openai import OpenAI
from dotenv import load_dotenv

# ============================================================
# ⚙️ Configuración
# ============================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "text-embedding-3-small")

DATA_DIR = "data"
IN_PATH = os.path.join(DATA_DIR, "cbt_categories.json")
OUT_PATH = os.path.join(DATA_DIR, "cbt_embeddings.npy")
META_PATH = os.path.join(DATA_DIR, "cbt_categories_meta.json")

if not OPENAI_API_KEY:
    print("❌ Falta la variable OPENAI_API_KEY en .env")
    sys.exit(1)

client = OpenAI(api_key=OPENAI_API_KEY)

# ============================================================
# 📊 Utilidad: barra de progreso
# ============================================================
def progress_bar(current, total, width=40):
    progress = current / total
    filled = int(width * progress)
    bar = "█" * filled + "░" * (width - filled)
    print(f"\r[{bar}] {current}/{total} ({progress:.0%})", end="")

# ============================================================
# 🧠 Generar embeddings
# ============================================================
def embed_texts(texts):
    res = client.embeddings.create(model=OPENAI_MODEL, input=texts)
    return [d.embedding for d in res.data]

# ============================================================
# 🚀 Main
# ============================================================
def main():
    print("\n⚙️ Ejecutando category_embedder.py...\n")

    if not os.path.exists(IN_PATH):
        print(f"❌ No existe {IN_PATH}")
        sys.exit(1)

    print(f"📖 Cargando categorías desde {IN_PATH} ...")
    with open(IN_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    categories = []
    for cid, cdata in data.items():
        name = cdata.get("name", "").strip()
        if name:
            categories.append((cid, name))

    total = len(categories)
    print(f"📦 {total} categorías detectadas. Generando embeddings...\n")

    names = [c[1] for c in categories]
    embeddings = []
    batch_size = 100

    for i in range(0, total, batch_size):
        batch = names[i:i + batch_size]
        emb = embed_texts(batch)
        embeddings.extend(emb)
        progress_bar(i + len(batch), total)
        time.sleep(0.05)

    print("\n\n✅ Proceso completado.")

    np.save(OUT_PATH, np.array(embeddings))
    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(categories, f, ensure_ascii=False, indent=2)

    print(f"💾 Embeddings guardados en: {OUT_PATH}")
    print(f"💾 Metadatos guardados en: {META_PATH}")
    print("✅ Listo para usar con category_matcher.py\n")

if __name__ == "__main__":
    main()