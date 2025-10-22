#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
category_matcher_plus.py
Versión avanzada del matcher: combina embeddings locales + razonamiento IA.
Autor: Felipe Melucci + GPT-5
"""

import json
import numpy as np
import sys
import openai
from openai import OpenAI
from pathlib import Path
from sklearn.metrics.pairwise import cosine_similarity

# ────────────────────────────────────────────────────────────────
# CONFIG
# ────────────────────────────────────────────────────────────────
DATA_DIR = Path("data")
LOGS_DIR = Path("logs/categories")
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Detecta automáticamente nombres de archivo
EMB_PATH = None
TXT_PATH = None
for emb in ["data/cbt_embeddings.npy", "data/category_embeddings.npy"]:
    if Path(emb).exists():
        EMB_PATH = emb
for meta in ["data/cbt_categories_meta.json", "data/category_texts.json"]:
    if Path(meta).exists():
        TXT_PATH = meta

if EMB_PATH is None or TXT_PATH is None:
    print("❌ No se encontraron embeddings o metadatos.")
    sys.exit(1)

client = OpenAI()

# ────────────────────────────────────────────────────────────────
# FUNCIONES
# ────────────────────────────────────────────────────────────────

def load_embeddings():
    print(f"📦 Cargando embeddings desde {EMB_PATH}")
    X = np.load(EMB_PATH)
    with open(TXT_PATH, "r", encoding="utf-8") as f:
        meta = json.load(f)
    texts = [m.get("full_name", m.get("name", "")) for m in meta]
    ids = [m.get("id") for m in meta]
    return X, texts, ids


def get_product_info(asin):
    path = Path(f"outputs/json/{asin}.json")
    if not path.exists():
        print(f"❌ No existe el archivo {path}")
        sys.exit(1)
    data = json.loads(path.read_text())
    title = data.get("attributes", {}).get("item_name", [{}])[0].get("value", "")
    bullets = [b.get("value") for b in data.get("attributes", {}).get("bullet_point", [])]
    desc = " ".join(bullets)
    return title, desc, data


def find_top_k_categories(query, embeddings, texts, ids, k=5):
    from openai import embeddings as emb_mod
    emb = client.embeddings.create(model="text-embedding-3-small", input=query).data[0].embedding
    sims = cosine_similarity([emb], embeddings)[0]
    top_idx = np.argsort(sims)[::-1][:k]
    return [(ids[i], texts[i], float(sims[i])) for i in top_idx]


def refine_with_ai(title, desc, candidates):
    prompt = f"""
You are an expert in e-commerce category classification.
A product with the following information must be matched to the most appropriate Mercado Libre Global Selling category.

Product title:
"{title}"

Product description (summarized):
"{desc[:600]}"

Candidate categories (with similarity scores):
{json.dumps(candidates, indent=2)}

Choose the **single best category** that most precisely fits this product and explain your reasoning briefly.
Return a JSON like:
{{
  "final_category_id": "...",
  "final_category_name": "...",
  "reason": "..."
}}
"""
    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "system", "content": "You are a professional e-commerce taxonomy expert."},
                  {"role": "user", "content": prompt}],
        temperature=0
    )
    try:
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception:
        return {"error": response.choices[0].message.content}


def main():
    if len(sys.argv) < 2:
        print("Uso: python3 category_matcher_plus.py <ASIN>")
        sys.exit(1)

    asin = sys.argv[1]
    embeddings, texts, ids = load_embeddings()
    title, desc, product_data = get_product_info(asin)

    print(f"\n🔍 Producto: {title}")
    print("🧠 Buscando categorías más cercanas por embeddings...")

    top5 = find_top_k_categories(title, embeddings, texts, ids, k=5)
    print("\n🏆 Top 5 coincidencias por similitud:")
    for cid, cname, sim in top5:
        print(f"   • {cname} ({cid}) → {sim:.3f}")

    print("\n🤖 Refinando con IA...")
    refined = refine_with_ai(title, desc, top5)

    out_path = LOGS_DIR / f"{asin}_category_plus.json"
    result = {
        "asin": asin,
        "title": title,
        "candidates": [{"id": c[0], "name": c[1], "similarity": c[2]} for c in top5],
        "refined_result": refined
    }
    out_path.write_text(json.dumps(result, indent=2))
    print(f"\n💾 Guardado en {out_path}")

    if "final_category_name" in refined:
        print(f"\n✅ Categoría final elegida: {refined['final_category_name']} ({refined['final_category_id']})")
        print(f"📝 Motivo: {refined['reason']}")
    else:
        print(f"\n⚠️ Error interpretando respuesta: {refined}")

# ============================================================
# 🧩 Función pública: match_category (para otros módulos)
# ============================================================
def match_category(ai_category: str, asin: str = None):
    """
    Dada una categoría detectada por IA (por ejemplo "Water Filter" o "LEGO Set"),
    busca el embedding más similar en el árbol local de categorías CBT.
    Devuelve un diccionario con los datos de la categoría y similitud.
    """
    import numpy as np, os, json
    from openai import OpenAI
    from numpy.linalg import norm

    EMB_PATH = "data/category_embeddings.npy"
    META_PATH = "data/category_texts.json"

    if not os.path.exists(EMB_PATH) or not os.path.exists(META_PATH):
        print("❌ Faltan embeddings o metadatos. Ejecutá primero: category_embedder.py")
        return None

    embeddings = np.load(EMB_PATH)
    meta = json.load(open(META_PATH, "r", encoding="utf-8"))

    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY", ""))

    emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=ai_category
    ).data[0].embedding

    scores = np.dot(embeddings, emb) / (norm(embeddings, axis=1) * norm(emb))
    idx = int(np.argmax(scores))
    best = meta[idx]
    best_score = float(scores[idx])

    # ✅ mejora: soporta listas o dicts
    if isinstance(best, dict):
        cat_id = best.get("id") or best.get("category_id")
        cat_name = best.get("name") or best.get("category_name")
    elif isinstance(best, list) and len(best) >= 2:
        cat_id, cat_name = best[0], best[1]
    else:
        cat_id, cat_name = str(best), str(best)

    result = {
        "matched_category_id": cat_id,
        "matched_category_name": cat_name,
        "similarity": best_score
    }

    if asin:
        os.makedirs("logs/categories", exist_ok=True)
        out_path = f"logs/categories/{asin}_category.json"
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

    return result

# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    main()