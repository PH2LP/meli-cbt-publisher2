#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 📦 publisher_from_transform_global_like.py — versión espejo del main global
# ============================================================

import os, sys, json, time, requests, datetime
from dotenv import load_dotenv

# ---------- Inicialización ----------
if sys.prefix == sys.base_prefix:
    vpy = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(vpy):
        print(f"⚙️ Activando entorno virtual automáticamente desde: {vpy}")
        os.execv(vpy, [vpy] + sys.argv)

load_dotenv()
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN")
API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}", "Content-Type": "application/json"}

# ---------- Helpers ----------
def http_get(url):
    r = requests.get(url, headers=HEADERS, timeout=30)
    if not r.ok:
        raise RuntimeError(f"GET {url} → {r.status_code} {r.text}")
    return r.json()

def http_post(url, body):
    r = requests.post(url, headers=HEADERS, json=body, timeout=60)
    if not r.ok:
        raise RuntimeError(f"POST {url} → {r.status_code} {r.text}")
    return r.json()

def http_put(url, body):
    r = requests.put(url, headers=HEADERS, json=body, timeout=60)
    if not r.ok:
        print(f"⚠️ PUT {url} → {r.status_code} {r.text}")
    return r.json() if r.text else {}

def get_sites_to_sell():
    uid = http_get(f"{API}/users/me").get("id")
    res = http_get(f"{API}/marketplace/users/{uid}")
    sites = [{"site_id": m["site_id"], "logistic_type": m.get("logistic_type", "remote")}
             for m in res.get("marketplaces", []) if m.get("site_id")]
    print(f"🌍 Sites: {sites}")
    return sites

# ============================================================
# 🚀 Publicador principal (igual formato que main global)
# ============================================================

def publish_from_transform(path):
    if not os.path.exists(path):
        raise FileNotFoundError(f"No existe el archivo: {path}")

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\n🔄 Procesando {os.path.basename(path)} ...")

    user = http_get(f"{API}/users/me")
    print(f"👤 Usuario: {user.get('nickname')} ({user.get('id')})")

    sites = get_sites_to_sell()

    # --- Defaults seguros ---
    pictures = data.get("pictures") or [
        {"source": "https://http2.mlstatic.com/D_NQ_NP_2X_915818-MLA74903469733_032024-F.webp"}
    ]
    sale_terms = data.get("sale_terms") or [
        {"id": "WARRANTY_TYPE", "value_id": "2230280", "value_name": "Seller warranty"},
        {"id": "WARRANTY_TIME", "value_name": "30 days"},
    ]

    # --- Valores obligatorios ---
    L = float(data.get("package_length") or 10.0)
    W = float(data.get("package_width") or 10.0)
    H = float(data.get("package_height") or 10.0)
    KG = float(data.get("package_weight") or 0.5)
    net = float(data.get("global_net_proceeds") or data.get("prices", {}).get("price_with_markup_usd") or 99.0)

    # Normalizar nombres de claves por si vienen en camelCase
for alt in ["packageLength", "packageWidth", "packageHeight", "packageWeight"]:
    val = data.get(alt)
    if val and f"package_{alt[7:].lower()}" not in data:
        data[f"package_{alt[7:].lower()}"] = val

    body = {
        "title": data.get("title")[:60],
        "category_id": data.get("category_id"),
        "currency_id": "USD",
        "available_quantity": 10,
        "condition": "new",
        "listing_type_id": "gold_pro",
        "buying_mode": "buy_it_now",
        "description": data.get("description"),
        "package_length": L,
        "package_width": W,
        "package_height": H,
        "package_weight": KG,
        "attributes": data.get("attributes", []),
        "sale_terms": sale_terms,
        "pictures": pictures,
        "seller_custom_field": data.get("seller_custom_field"),
        "global_net_proceeds": net,
        "_source_price": data.get("prices", {}).get("base_price_usd"),
        "_net_proceeds": net,
        "sites_to_sell": sites,
    }

    print("🚀 POST /global/items ...")
    res = http_post(f"{API}/global/items", body)
    item_id = res.get("id") or res.get("resource", "").split("/")[-1]
    print(f"✅ Publicado correctamente: {item_id}")

    # --- Refuerzo SKU + descripción ---
    if item_id:
        put_body = {
            "seller_custom_field": data.get("seller_custom_field"),
            "description": data.get("description"),
            "site_id": sites[0]["site_id"],
            "logistic_type": sites[0]["logistic_type"],
        }
        try:
            print("🛠️ Aplicando SKU/desc con PUT ...")
            http_put(f"{API}/global/items/{item_id}", put_body)
        except Exception as e:
            print(f"⚠️ PUT fallback error: {e}")

    # --- Log publicación ---
    os.makedirs("logs/published", exist_ok=True)
    log = {
        "timestamp": datetime.datetime.now().isoformat(),
        "item_id": item_id,
        "title": data.get("title"),
        "price": net,
        "category_id": data.get("category_id"),
        "asin": data.get("asin"),
    }
    with open(f"logs/published/{item_id or int(time.time())}.json", "w", encoding="utf-8") as f:
        json.dump(log, f, indent=2, ensure_ascii=False)
    print(f"📝 Guardado log → logs/published/{item_id}.json")

# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Uso: python3 publisher_from_transform_global_like.py <archivo.json>")
        sys.exit(1)
    path = sys.argv[1]
    try:
        publish_from_transform(path)
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        print("\n✅ Proceso completo.")


if __name__ == "__main__":
    main()