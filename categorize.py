#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 🤖 categorize.py (v5.5)
# Detecta la categoría base del producto a partir del JSON de Amazon
# Preparado para integrarse con embeddings locales de MercadoLibre CBT
# ============================================================

import os, sys, json, requests, subprocess
from dotenv import load_dotenv
from openai import OpenAI

# ============================================================
# 🧠 Autoactivar entorno virtual
# ============================================================
def auto_activate_venv():
    venv_python = os.path.join(os.getcwd(), "venv", "bin", "python")
    if os.path.exists(venv_python) and sys.executable != venv_python:
        print(f"⚙️ Activando entorno virtual automáticamente desde: {venv_python}")
        subprocess.call([venv_python] + sys.argv)
        sys.exit(0)
auto_activate_venv()

# ============================================================
# ⚙️ Configuración inicial
# ============================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
CACHE_DIR = "logs/categories"

# ============================================================
# 📘 Utilidades
# ============================================================
def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def flatten_json(data, prefix="", out=None):
    """Aplana el JSON profundamente para poder buscar claves fácilmente."""
    if out is None:
        out = {}
    if isinstance(data, dict):
        for k, v in data.items():
            flatten_json(v, f"{prefix}.{k}" if prefix else k, out)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            flatten_json(v, f"{prefix}[{i}]", out)
    else:
        out[prefix] = str(data)
    return out

# ============================================================
# 🧠 IA: clasificación corta y precisa
# ============================================================
def ai_classify_category(title: str):
    if not client:
        return "Unknown"
    prompt = f"""
You are a product classification AI for e-commerce.
Your task is to identify the **main product category** from the given title, in clear **English**.

Follow these strict rules:
- Output must be **1 to 3 words only**, in singular form.
- Do NOT include brand names, models, specs, colors, or features.
- Focus only on what the product **is**.
- Return only the category name, no explanations.

Examples:
- "LEGO Bouquet of Flowers Building Kit" → "LEGO Set"
- "Stanley 120-Piece Tool Set" → "Tool Set"
- "iPhone 14 Pro Max Case" → "Phone Case"
- "Everpure H-104 Drinking Water System" → "Water Filter"
- "DeWalt Cordless Drill 20V" → "Drill"
- "PlayStation 5 Console Bundle" → "Video Game Console"
- "MacBook Pro 2027 M3 Chip" → "Laptop"
- "Whirlpool Microwave Oven 500W" → "Microwave Oven"
- "Dyson V11 Cordless Vacuum Cleaner" → "Vacuum Cleaner"
- "Canon EOS R50 Mirrorless Camera" → "Digital Camera"
- "Adidas Ultraboost 23 Running Shoes" → "Running Shoes"
- "KitchenAid Artisan Stand Mixer" → "Stand Mixer"
- "HP LaserJet Pro Printer" → "Printer"
- "Apple AirPods Pro 2nd Gen" → "Wireless Earbuds"
- "Samsung 4K Smart TV 55 inch" → "Television"
- "LEGO Star Wars Millennium Falcon" → "LEGO Set"
- "Nintendo Switch OLED Console" → "Video Game Console"

Now classify this product:
Title: {title}

Return only the category name in English.
"""
    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
        )
        return r.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Error in AI classification: {e}")
        return "Unknown"

# ============================================================
# 🚀 Proceso principal
# ============================================================
def categorize_product(json_path):
    if not os.path.exists(json_path):
        for base in ["outputs/json", "outputs"]:
            candidate = os.path.join(base, os.path.basename(json_path))
            if os.path.exists(candidate):
                json_path = candidate
                break
    if not os.path.exists(json_path):
        print(f"❌ File not found: {json_path}")
        sys.exit(1)

    data = load_json(json_path)
    asin = data.get("asin", os.path.basename(json_path).split(".")[0])
    cache_path = f"{CACHE_DIR}/{asin}_category.json"

    # 🧠 Cache
    if os.path.exists(cache_path):
        print(f"♻️ Using cached category: {cache_path}\n")
        result = load_json(cache_path)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    flat = flatten_json(data)

    # 🔍 Posibles claves de título
    possible_keys = [
        "attributes.item_name[0].value",
        "attribute_sets[0].item_name",
        "attribute_sets[0].title",
        "summaries[0].itemName",
        "summaries[0].productTitle",
        "attribute_sets[0].productTitle",
        "attributes.title[0].value",
        "attributes.item_title[0].value",
        "productInfo.title",
        "product_title",
        "item_name",
        "title",
        "display_name",
        "name",
        "product_name",
        "product_label",
        "product_summary.title",
        "details.title",
    ]

    title = None
    for key in possible_keys:
        for fk, v in flat.items():
            if key.lower() in fk.lower() and len(str(v)) > 5:
                title = v
                break
        if title:
            break

    # Fallback → texto razonable
    if not title:
        candidates = [
            v for v in flat.values()
            if isinstance(v, str)
            and len(v) > 10
            and not v.lower().startswith(("en_", "es_", "fr_"))
        ]
        title = candidates[0] if candidates else "Unknown Product"

    print(f"\n🔍 Analyzing product:\n🧱 Title: {title}\n")

    # 1️⃣ IA genera categoría base
    ai_cat = ai_classify_category(title)
    print(f"🤖 AI category guess: {ai_cat}")

    # 2️⃣ (Luego se integrará con embeddings)
    found = None

    result = {
        "asin": asin,
        "title": title,
        "ai_category": ai_cat,
        "category_id": found.get("category_id") if found else None,
        "category_name": found.get("category_name") if found else None,
        "site": found.get("site") if found else None,
    }

    save_json(cache_path, result)
    print(f"\n💾 Saved to cache: {cache_path}")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result

# ============================================================
# 🧩 CLI (robusto)
# ============================================================
if __name__ == "__main__":
    print("🔧 categorize.py started")
    if len(sys.argv) < 2:
        print("⚠️ Usage: python3 categorize.py <amazon_json_path>")
        sys.exit(1)

    json_path = sys.argv[1]
    print(f"📂 Input path: {json_path}")
    try:
        categorize_product(json_path)
    except Exception as e:
        import traceback
        print("❌ ERROR during execution:")
        print(traceback.format_exc())