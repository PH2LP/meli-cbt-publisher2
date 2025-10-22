#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 🧠 transform_mapper_new.py (v3.0 FULL AUTO + API READY)
# Amazon → MercadoLibre attribute translator + AI Category Detection
# ============================================================

import os, sys, json, re, requests
from typing import Dict, List, Any

# ---------- 0) Auto-activar entorno virtual ----------
if sys.prefix == sys.base_prefix:
    vpy = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(vpy):
        print(f"⚙️ Activando entorno virtual automáticamente desde: {vpy}")
        os.execv(vpy, [vpy] + sys.argv)

# ---------- 1) Carga entorno ----------
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("🌎 .env cargado (si existe)")
except Exception:
    pass

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ML_ACCESS_TOKEN = os.getenv("ML_ACCESS_TOKEN", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MARKUP_PCT = float(os.getenv("MARKUP_PCT", "35")) / 100.0

from openai import OpenAI
from category_matcher import match_category   # ← integración directa aquí

client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"} if ML_ACCESS_TOKEN else {}

CACHE_PATH = "logs/ai_equivalences_cache.json"
TITLE_CACHE_PATH = "logs/ai_title_cache.json"
DESC_CACHE_PATH  = "logs/ai_desc_cache.json"

def _load_small_cache(path):
    try:
        if os.path.exists(path):
            return json.load(open(path, "r", encoding="utf-8"))
    except:
        pass
    return {}

def _save_small_cache(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ============================================================
# 📘 Utilidades básicas
# ============================================================
def load_json_file(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json_file(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def flatten_summary(data, prefix="", out=None):
    """Aplana profundamente un JSON (incluye arrays y subclaves)"""
    if out is None:
        out = {}
    if isinstance(data, dict):
        for k, v in data.items():
            flatten_summary(v, f"{prefix}.{k}" if prefix else k, out)
    elif isinstance(data, list):
        for i, v in enumerate(data):
            flatten_summary(v, f"{prefix}[{i}]", out)
    else:
        val = str(data).strip()
        if not val or val.lower() in {"none","null","en_us","default","n/a","unknown","generic"}:
            return out
        if isinstance(data, (str, int, float)) and len(val) <= 200:
            out[prefix.lower()] = val
    return out

def extract_number(s):
    m = re.search(r"-?\d+(\.\d+)?", str(s))
    return float(m.group(0)) if m else None

def normalize_key(k:str)->str:
    return re.sub(r"[\s_\-\[\]\.]+","",k.lower())

def _norm_unit(u:str)->str:
    u = str(u).strip().lower()
    m = {
        "centimeters":"cm","centimeter":"cm","cm":"cm",
        "millimeters":"mm","millimeter":"mm","mm":"mm",
        "meters":"m","meter":"m","m":"m",
        "inches":"in","inch":"in","in":"in",
        "kilograms":"kg","kilogram":"kg","kg":"kg",
        "grams":"g","gram":"g","g":"g",
        "pounds":"lb","pound":"lb","lb":"lb","lbs":"lb",
        "ounces":"oz","ounce":"oz","oz":"oz"
    }
    return m.get(u, u)

def _to_cm(value, unit):
    unit = _norm_unit(unit)
    if value is None: return None
    if unit == "cm": return value
    if unit == "mm": return value / 10.0
    if unit == "m":  return value * 100.0
    if unit == "in": return value * 2.54
    return value

def _to_kg(value, unit):
    unit = _norm_unit(unit)
    if value is None: return None
    if unit == "kg": return value
    if unit == "g":  return value / 1000.0
    if unit == "lb": return value * 0.45359237
    if unit == "oz": return value * 0.028349523125
    return value

    # ============================================================
# 🔍 Categoría automática (IA + embeddings locales)
# ============================================================
def improve_title_with_ai(title, brand=None, model=None):
    if not client:
        return title
    try:
        prompt = f"""Devuelve un título corto y limpio (máx 80) en español LATAM.
- Mantén marca y modelo si existen.
- Sin emojis ni HTML.
Título base: {title}
Marca: {brand or ''}
Modelo: {model or ''}"""
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.2,
            messages=[{"role":"user","content":prompt}],
        )
        return resp.choices[0].message.content.strip()[:80]
    except Exception:
        return title


def predict_category(title, amazon_json):
    """
    Integra IA + embeddings para determinar categoría CBT de forma totalmente local.
    """
    print("🧭 Buscando categoría con embeddings + IA…")
    try:
        if not client:
            ai_category = "Unknown"
        else:
            prompt = f"""Dado este título, devuelve una sola categoría corta y genérica en inglés:
Ejemplos: "Water Filter", "LEGO Set", "Hair Dryer", "Dog Toy", "Garden Hose".
Título: {title}"""
            ai_resp = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0,
                messages=[
                    {"role": "system", "content": "You are a concise product classifier."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=15,
            )
            ai_category = ai_resp.choices[0].message.content.strip()
        print(f"🤖 IA guess: {ai_category}")

        match = match_category(ai_category, amazon_json.get("asin", "unknown"))
        cat_id = match.get("matched_category_id", "CBT1157")
        cat_name = match.get("matched_category_name", "Default")
        print(f"✅ Categoría más cercana: {cat_name} ({cat_id}) | Similitud {match.get('similarity'):.3f}")
        return cat_id
    except Exception as e:
        print(f"⚠️ Error detectando categoría: {e}")
        return "CBT1157"


# ============================================================
# 📗 Obtener schema
# ============================================================
def get_category_schema(category_id):
    try:
        r = requests.get(f"{API}/categories/{category_id}/attributes",
                         headers=HEADERS, timeout=10)
        r.raise_for_status()
        schema = {}
        for a in r.json():
            if a.get("id"):
                schema[a["id"]] = {
                    "value_type": a.get("value_type"),
                    "values": {v["name"].lower(): v["id"]
                               for v in a.get("values",[]) if v.get("id")},
                    "allowed_units": [u["id"] for u in a.get("allowed_units",[])]
                                     if a.get("allowed_units") else []
                }
        print(f"📘 Schema obtenido: {len(schema)} atributos.")
        return schema
    except Exception as e:
        print(f"⚠️ No se pudo obtener schema {category_id}: {e}")
        return {}


# ============================================================
# 🔎 Buscar valor en flatten
# ============================================================
def find_value(flat, keys):
    if not keys:
        return None
    if isinstance(keys, str):
        keys = [keys]
    if isinstance(keys, dict):
        new_keys = []
        for v in keys.values():
            if isinstance(v, str):
                new_keys.append(v)
            elif isinstance(v, list):
                new_keys.extend([x for x in v if isinstance(x, str)])
        keys = new_keys
    keys = [k for k in keys if isinstance(k, str)]
    if not keys:
        return None

    norm_flat = {normalize_key(fk): v for fk, v in flat.items()}
    for key in keys:
        nk = normalize_key(key)
        for fk, v in norm_flat.items():
            if nk in fk or fk in nk:
                return v
    return None


# ============================================================
# 🧭 Diccionario ampliado de claves de dimensiones de PAQUETE
# ============================================================
PACKAGE_DIMENSION_KEYS = {
    "length": [
        "attributes.item_package_dimensions[0].length.value",
        "package_dimensions.length", "item_package_length", "package_length",
        "shipping_dimensions.length", "outer_dimensions.length", "outer_carton_dimensions.length",
        "outer_package_length", "box_length", "parcel_length"
    ],
    "width": [
        "attributes.item_package_dimensions[0].width.value",
        "package_dimensions.width", "item_package_width", "package_width",
        "shipping_dimensions.width", "outer_dimensions.width", "outer_carton_dimensions.width",
        "outer_package_width", "box_width", "parcel_width"
    ],
    "height": [
        "attributes.item_package_dimensions[0].height.value",
        "package_dimensions.height", "item_package_height", "package_height",
        "shipping_dimensions.height", "outer_dimensions.height", "outer_carton_dimensions.height",
        "outer_package_height", "box_height", "parcel_height"
    ],
    "weight": [
        "attributes.item_package_weight[0].value",
        "item_package_weight", "package_weight", "shipping_weight",
        "package_dimensions.weight", "outer_package_weight", "carton_weight",
        "gross_weight", "boxed_weight", "parcel_weight"
    ]
}
# ============================================================
# 📦 Extraer dimensiones del PAQUETE (solo paquete)
# ============================================================
def get_package_dimension(flat, kind):
    kind = kind.lower()
    norm_flat = {normalize_key(k): v for k, v in flat.items()}

    value_candidates = [
        f"attributes.item_package_dimensions[0].{kind}.value",
        f"item_package_dimensions.{kind}.value",
        f"package_dimensions.{kind}.value",
        f"shipping_dimensions.{kind}.value",
        f"outer_package_dimensions.{kind}.value",
        f"{kind}.value",
    ]
    unit_candidates = [
        f"attributes.item_package_dimensions[0].{kind}.unit",
        f"item_package_dimensions.{kind}.unit",
        f"package_dimensions.{kind}.unit",
        f"shipping_dimensions.{kind}.unit",
        f"outer_package_dimensions.{kind}.unit",
        f"{kind}.unit",
    ]

    val = None
    unit = None
    for c in value_candidates:
        nk = normalize_key(c)
        for fk, v in norm_flat.items():
            if nk in fk:
                val = extract_number(v)
                if val is not None:
                    break
        if val is not None:
            break

    for c in unit_candidates:
        nk = normalize_key(c)
        for fk, v in norm_flat.items():
            if nk in fk:
                unit = str(v).strip()
                break
        if unit:
            break

    if val is not None:
        if kind == "weight":
            val = _to_kg(val, unit or "kg")
            return {"number": round(float(val), 3), "unit": "kg"}
        else:
            val = _to_cm(val, unit or "cm")
            return {"number": round(float(val), 2), "unit": "cm"}

    for c in PACKAGE_DIMENSION_KEYS.get(kind, []):
        nk = normalize_key(c)
        for fk, v in norm_flat.items():
            if nk in fk:
                num = extract_number(v)
                if num is not None:
                    if kind == "weight":
                        return {"number": round(float(_to_kg(num, "kg")), 3), "unit": "kg"}
                    return {"number": round(float(_to_cm(num, "cm")), 2), "unit": "cm"}

    print(f"⚠️ No se encontró {kind} del paquete en el JSON (ni valor ni unidad).")
    return None


# ============================================================
# 🧩 Diccionario base (inicial)
# ============================================================
BASE_EQUIV = {
    "BRAND":["brand","manufacturer","brand_name","attributes.brand[0].value","summaries[0].brandname"],
    "MODEL":["model","model_number","item_model_number","attributes.model_number[0].value"],
    "COLOR":["color","color_name","attributes.color[0].value"],
    "MATERIAL":["material","materials","attributes.material[0].value"],
    "TOY_MATERIALS":["material","materials"],
    "PIECES_NUMBER":["number_of_pieces","numberOfPieces","attributes.number_of_pieces[0].value"],
    "WEIGHT":["weight","item_weight","shipping_weight","attributes.item_weight[0].value"],
    "HEIGHT":["height","item_height","dimensions.height","attributes.item_dimensions[0].height.value"],
    "WIDTH":["width","item_width","dimensions.width","attributes.item_dimensions[0].width.value"],
    "LENGTH":["length","item_length","dimensions.length","attributes.item_dimensions[0].length.value"],
    "CATALOG_TITLE":["title","product_title","item_name","summaries[0].itemName"],
    "RECOMMENDED_AGE_GROUP":["age_range","recommended_age","ageRange","attributes.recommended_age_range[0].value"],
}

# ============================================================
# 🧠 Cache persistente
# ============================================================
def load_cache():
    if os.path.exists(CACHE_PATH):
        try:
            return json.load(open(CACHE_PATH))
        except:
            return {}
    return {}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH), exist_ok=True)
    with open(CACHE_PATH,"w",encoding="utf-8") as f:
        json.dump(cache, f, indent=2, ensure_ascii=False)


# ============================================================
# 🤖 IA equivalencias
# ============================================================
def ask_gpt_equivalences(category_id, missing, flat, cache):
    if not client:
        return {}
    new_missing = [m for m in missing if m not in cache.keys()]
    if not new_missing:
        print("♻️ Todos los atributos faltantes ya están en cache, no se consulta IA.")
        return {}

    summary = "\n".join(f"{k}: {v}" for k,v in list(flat.items())[:220])
    prompt = f"""
Encuentra equivalencias entre atributos de MercadoLibre y el JSON de Amazon.
Categoría: {category_id}
Atributos faltantes:
{new_missing}
JSON Amazon (resumen):
{summary}
Reglas:
- Usa claves reales del JSON, no inventes.
- Devuelve JSON con formato:
{{"equivalences": {{"COLOR":["color"],"MATERIAL":["material"], ...}}}}
"""
    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[{"role":"user","content":prompt}],
        )
        txt = r.choices[0].message.content.strip()
        m = re.search(r"\{.*\}", txt, re.S)
        if not m:
            return {}
        data = json.loads(m.group(0))
        eqs = data.get("equivalences", {})
        if eqs:
            for k,v in eqs.items():
                cache[k] = v
            save_cache(cache)
            print(f"💾 {len(eqs)} nuevas equivalencias aprendidas y guardadas.")
        else:
            print("⚠️ La IA no devolvió equivalencias válidas.")
        return eqs
    except Exception as e:
        print(f"⚠️ Error IA equivalences: {e}")
        return {}


# ============================================================
# 📝 IA título + descripción
# ============================================================
def _first(data, paths):
    flat = flatten_summary(data)
    for p in paths:
        for k,v in flat.items():
            if normalize_key(p) in normalize_key(k):
                return v
    return None

def _list_from(data, paths):
    flat = flatten_summary(data)
    out=[]
    for p in paths:
        for k,v in flat.items():
            if normalize_key(p) in normalize_key(k):
                out.append(v)
    return out

def _dims_hint(data):
    flat=flatten_summary(data)
    for k,v in flat.items():
        if "itempackagedimensions" in normalize_key(k) or "packagedimensions" in normalize_key(k):
            return f"{k}:{v}"
    return ""


def generate_ai_title(asin: str, amazon_json: dict, max_chars=60)->str:
    base = amazon_json.get("item_name") or amazon_json.get("title") or "Producto"
    if not client:
        return base[:max_chars]

    cache = _load_small_cache(TITLE_CACHE_PATH)
    if asin and asin in cache:
        return cache[asin]

    brand = _first(amazon_json, ["brandName","brand","attributes.brand[0].value","summaries[0].brandName"])
    model = _first(amazon_json, ["model_name","model_number","model","summaries[0].modelNumber"])
    bullets = _list_from(amazon_json, ["attributes.bullet_point","bullet_point"])[:3]

    prompt = f"""Crea un título de máximo {max_chars} caracteres en español LATAM, claro y vendedor.
Incluye marca y modelo si están. Sin emojis ni HTML.
Base: {base}
Marca: {brand}
Modelo: {model}
Bullets: {bullets}"""
    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL, temperature=0.3,
            messages=[{"role":"user","content":prompt}],
        )
        title = (r.choices[0].message.content or "").strip()[:max_chars]
        if asin:
            cache[asin]=title
            _save_small_cache(TITLE_CACHE_PATH, cache)
        return title or base[:max_chars]
    except:
        return base[:max_chars]


def generate_ai_description(asin: str, amazon_json: dict)->str:
    if not client:
        return ""
    cache = _load_small_cache(DESC_CACHE_PATH)
    if asin and asin in cache:
        return cache[asin]

    brand   = _first(amazon_json, ["brandName","brand","attributes.brand[0].value","summaries[0].brandName"])
    model   = _first(amazon_json, ["model_name","model_number","model","summaries[0].modelNumber"])
    pieces  = _first(amazon_json, ["number_of_pieces","attributes.number_of_pieces[0].value"])
    color   = _first(amazon_json, ["color","attributes.color[0].value"])
    material= _first(amazon_json, ["material","attributes.material[0].value"])
    bullets = _list_from(amazon_json, ["attributes.bullet_point","bullet_point"])[:8]
    dims_pkg= _dims_hint(amazon_json)

    prompt = f"""Redacta una descripción larga (≥3 párrafos) en español LATAM, persuasiva y clara, para Mercado Libre.
Incluye beneficios y especificaciones relevantes sin inventar. Sin HTML, solo texto plano.
Datos:
- Marca: {brand} | Modelo: {model} | Piezas: {pieces}
- Color: {color} | Material: {material}
- Puntos: {bullets}
- Pista dimensiones paquete: {dims_pkg}
Cierra con un llamado a la acción suave."""
    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL, temperature=0.4,
            messages=[{"role":"user","content":prompt}],
        )
        desc = (r.choices[0].message.content or "").strip()
        if asin:
            cache[asin]=desc
            _save_small_cache(DESC_CACHE_PATH, cache)
        return desc
    except:
        return ""

        # ============================================================
# 💵 Precio base + Markup
# ============================================================
def _read_number(x, default=None):
    try:
        if isinstance(x, (int, float)):
            return float(x)
        return float(str(x).replace("$", "").strip())
    except:
        return default

def _try_paths(d, paths: List[str]):
    flat = flatten_summary(d)
    for p in paths:
        nk = normalize_key(p)
        for k, v in flat.items():
            if nk in normalize_key(k):
                val = _read_number(v)
                if val is not None:
                    return val
    return None

def get_amazon_base_price(amazon_json) -> float:
    candidates = [
        "attributes.list_price[0].value",
        "offers.listings[0].price.amount",
        "price.value",
        "summaries[0].listprice.value",
        "attributes.suggested_lower_price_plus_shipping[0].value",
        "price",
    ]
    price = _try_paths(amazon_json, candidates)
    if price is None:
        price = 10.0
    return round(float(price), 2)

def compute_price_with_markup(amazon_json) -> Dict[str, float]:
    base = get_amazon_base_price(amazon_json)
    net  = round(base * (1.0 + MARKUP_PCT), 2)
    return {"base_price_usd": base, "price_with_markup_usd": net}


# ============================================================
# 🔎 GTIN / ASIN
# ============================================================
def _extract_gtins(flat: dict) -> List[str]:
    gtins = []
    for k, v in flat.items():
        if "externally_assigned_product_identifier" in k and k.endswith(".value"):
            val = re.sub(r"\D", "", str(v))
            if val and 8 <= len(val) <= 14:
                gtins.append(val)
    if not gtins:
        raw = json.dumps(flat)
        for m in re.findall(r"\b\d{8,14}\b", raw):
            gtins.append(m)

    cleaned = []
    seen = set()
    for g in gtins:
        g_clean = g.lstrip("0") or g
        if g_clean not in seen:
            seen.add(g_clean)
            cleaned.append(g_clean)
    cleaned.sort()
    return cleaned

def _infer_asin_from_flat(flat: dict)->str|None:
    for k,v in flat.items():
        if k.endswith(".asin") or k.endswith(".ASIN") or k == "asin":
            return str(v).strip()
    return None


# ============================================================
# 🏗️ Construir atributos ML
# ============================================================
def build_meli_attributes(amazon_json, category_id):
    schema = get_category_schema(category_id)
    flat = flatten_summary(amazon_json)
    cache = load_cache()

    matched, missing = {}, []
    reused = 0

    asin = amazon_json.get("asin") or _infer_asin_from_flat(flat)
    if asin:
        matched["SELLER_SKU"] = asin

    gtins = _extract_gtins(flat)
    if gtins:
        matched["GTIN"] = gtins[0]

    for kind, aid in {
        "length": "SELLER_PACKAGE_LENGTH",
        "width": "SELLER_PACKAGE_WIDTH",
        "height": "SELLER_PACKAGE_HEIGHT",
        "weight": "SELLER_PACKAGE_WEIGHT",
    }.items():
        dim = get_package_dimension(flat, kind)
        if dim:
            matched[aid] = dim

    for aid, meta in schema.items():
        if aid in matched:
            continue
        keys = BASE_EQUIV.get(aid, [])
        val = find_value(flat, keys) if keys else None
        if not val and aid in cache:
            val = find_value(flat, cache[aid])
            if val:
                reused += 1
        if val:
            matched[aid] = val
        else:
            missing.append(aid)

    if missing:
        cached_before = [m for m in missing if m in cache]
        new_to_ask = [m for m in missing if m not in cache]
        if cached_before:
            print(f"♻️ Reusando {len(cached_before)} equivalencias del cache.")
        if new_to_ask:
            print(f"🤖 Pidiendo equivalencias IA solo para {len(new_to_ask)} nuevas…")
            new_eq = ask_gpt_equivalences(category_id, new_to_ask, flat, cache)
            for k,v in new_eq.items():
                val = find_value(flat, v)
                if val:
                    matched[k] = val

    pkg_l = (matched.get("SELLER_PACKAGE_LENGTH") or {}).get("number")
    pkg_w = (matched.get("SELLER_PACKAGE_WIDTH") or {}).get("number")
    pkg_h = (matched.get("SELLER_PACKAGE_HEIGHT") or {}).get("number")
    pkg_wt= (matched.get("SELLER_PACKAGE_WEIGHT") or {}).get("number")
    if all([pkg_l, pkg_w, pkg_h, pkg_wt]):
        print(f"📦 Paquete: {pkg_l:.2f}×{pkg_w:.2f}×{pkg_h:.2f} cm – {pkg_wt:.3f} kg")

    prices = compute_price_with_markup(amazon_json)
    print(f"💰 Precio base: ${prices['base_price_usd']:.2f} → con markup ({int(MARKUP_PCT*100)}%): ${prices['price_with_markup_usd']:.2f}")

    title = generate_ai_title(asin or "", amazon_json, max_chars=60)
    description = generate_ai_description(asin or "", amazon_json)

    attrs=[]
    for aid,val in matched.items():
        meta=schema.get(aid,{})
        vtype=meta.get("value_type")
        a={"id":aid}
        if isinstance(val, dict) and "number" in val and "unit" in val:
            a["value_struct"] = {"number": float(val["number"]), "unit": val["unit"]}
        elif vtype=="number_unit":
            num=extract_number(val)
            unit=re.search(r"(cm|mm|kg|g|m|in|lb|oz)",str(val).lower())
            u=unit.group(1) if unit else (meta.get("allowed_units",[None])[0] or "cm")
            if "WEIGHT" in aid:
                num = _to_kg(num, u); u = "kg"
            elif aid.endswith(("LENGTH","WIDTH","HEIGHT")):
                num = _to_cm(num, u); u = "cm"
            if num is not None:a["value_struct"]={"number":float(num),"unit":u}
        elif vtype=="list":
            lower=str(val).lower()
            if lower in meta.get("values",{}):
                a["value_id"]=meta["values"][lower]
            else:a["value_name"]=val
        else:
            a["value_name"]=val
        attrs.append(a)

    print(f"\n📊 Resumen final → Atributos directos: {len(attrs)} | Faltantes IA: {len(missing)} | Cache reutilizado: {reused}")

        # =========================================
        # =========================================
    # ✅ FORMATO FINAL API-READY (CBT global item)
    #  - Campos obligatorios del endpoint /global/items
    #  - Usamos global_net_proceeds (NO price)
    #  - Nombres correctos para medidas de paquete
    # =========================================

        # =========================================
    # 🧹 Limpieza: eliminar duplicados de dimensiones dentro de attributes
    # =========================================
    clean_attrs = []
    for a in attrs:
        attr_id = a.get("id", "").upper()
        if attr_id in [
            "PACKAGE_LENGTH", "PACKAGE_WIDTH", "PACKAGE_HEIGHT", "PACKAGE_WEIGHT",
            "SELLER_PACKAGE_LENGTH", "SELLER_PACKAGE_WIDTH",
            "SELLER_PACKAGE_HEIGHT", "SELLER_PACKAGE_WEIGHT"
        ]:
            continue
        clean_attrs.append(a)
    attrs = clean_attrs

        # =========================================
        # 🧹 Limpieza: eliminar duplicados de dimensiones dentro de attributes
        # =========================================
    clean_attrs = []
    for a in attrs:
        attr_id = a.get("id", "").upper()
        if attr_id in [
            "PACKAGE_LENGTH", "PACKAGE_WIDTH", "PACKAGE_HEIGHT", "PACKAGE_WEIGHT",
            "SELLER_PACKAGE_LENGTH", "SELLER_PACKAGE_WIDTH",
            "SELLER_PACKAGE_HEIGHT", "SELLER_PACKAGE_WEIGHT"
        ]:
            continue
        clean_attrs.append(a)
    attrs = clean_attrs

    item_api = {
        "site_id": "CBT",                        # requerido por /global/items
        "logistic_type": "cross_docking",        # "cross_docking" o "fulfillment" según tu operación
        "category_id": category_id,
        "title": title,
        "currency_id": "USD",
        "available_quantity": 10,
        "buying_mode": "buy_it_now",
        "listing_type_id": "gold_special",       # o el que uses
        "condition": "new",

        # Descripción en el formato que espera la API
        "description": {"plain_text": description},

        # ⚠️ Nombres correctos exigidos por la API (no 'pack_*')
        "package_length": (matched.get("SELLER_PACKAGE_LENGTH") or {}).get("number", 0) or (pkg_l or 0),
        "package_width":  (matched.get("SELLER_PACKAGE_WIDTH")  or {}).get("number", 0) or (pkg_w or 0),
        "package_height": (matched.get("SELLER_PACKAGE_HEIGHT") or {}).get("number", 0) or (pkg_h or 0),
        "package_weight": (matched.get("SELLER_PACKAGE_WEIGHT") or {}).get("number", 0) or (pkg_wt or 0),

        # Atributos de ML (IDs oficiales del schema)
        "attributes": attrs,

        # Listas requeridas (aunque estén vacías)
        "sale_terms": [],
        "pictures": [],

        # SKU global
        "seller_custom_field": asin or "",

        # Publicación por net proceeds (no enviar 'price')
        "global_net_proceeds": prices["price_with_markup_usd"],
    }
    # 🔹 Agregamos compatibilidad CBT
    item_api["global_net_proceeds"] = prices["price_with_markup_usd"]

        # ============================================================
    # 🧹 POST-CLEANUP FINAL → Correcciones antes de guardar API-ready
    # ============================================================

    # 1️⃣ Redondear dimensiones (ML CBT solo acepta 2 decimales en package_weight)
    item_api["package_length"] = round(float(item_api.get("package_length", 0) or 0), 2)
    item_api["package_width"]  = round(float(item_api.get("package_width", 0) or 0), 2)
    item_api["package_height"] = round(float(item_api.get("package_height", 0) or 0), 2)
    item_api["package_weight"] = round(float(item_api.get("package_weight", 0) or 0), 2)

    # 2️⃣ Asegurar listing_type_id válido para CBT
    if item_api.get("listing_type_id") not in ["gold_pro", "gold_special"]:
        item_api["listing_type_id"] = "gold_pro"
    else:
        item_api["listing_type_id"] = "gold_pro"  # forzar siempre gold_pro

    # 3️⃣ Asegurar sale_terms válidos (no lista vacía)
    if not item_api.get("sale_terms"):
        item_api["sale_terms"] = [
            {"id": "WARRANTY_TYPE", "value_name": "Seller warranty"},
            {"id": "WARRANTY_TIME", "value_name": "30 days"}
        ]

    # 4️⃣ Asegurar al menos una imagen de fallback
    if not item_api.get("pictures"):
        item_api["pictures"] = [
            {"source": "https://http2.mlstatic.com/D_NQ_NP_2X_915818-MLA74903469733_032024-F.webp"}
        ]

    # 5️⃣ Limpieza por seguridad (sin nulos ni arrays vacíos)
    for k, v in list(item_api.items()):
        if v in [None, "", []]:
            if k not in ["sale_terms", "pictures"]:  # dejamos los requeridos
                item_api.pop(k, None)

                    # ============================================================
    # 🧹 POST-CLEANUP FINAL → Correcciones antes de guardar API-ready
    # ============================================================

    # 1️⃣ Redondear dimensiones (ML CBT solo acepta 2 decimales en package_weight)
    item_api["package_length"] = round(float(item_api.get("package_length", 0) or 0), 2)
    item_api["package_width"]  = round(float(item_api.get("package_width", 0) or 0), 2)
    item_api["package_height"] = round(float(item_api.get("package_height", 0) or 0), 2)
    item_api["package_weight"] = round(float(item_api.get("package_weight", 0) or 0), 2)

    # 2️⃣ Asegurar listing_type_id válido para CBT
    if item_api.get("listing_type_id") not in ["gold_pro", "gold_special"]:
        item_api["listing_type_id"] = "gold_pro"
    else:
        item_api["listing_type_id"] = "gold_pro"  # forzar siempre gold_pro

    # 3️⃣ Asegurar sale_terms válidos (no lista vacía)
    if not item_api.get("sale_terms"):
        item_api["sale_terms"] = [
            {"id": "WARRANTY_TYPE", "value_name": "Seller warranty"},
            {"id": "WARRANTY_TIME", "value_name": "30 days"}
        ]

    # 4️⃣ Asegurar al menos una imagen de fallback
    if not item_api.get("pictures"):
        item_api["pictures"] = [
            {"source": "https://http2.mlstatic.com/D_NQ_NP_2X_915818-MLA74903469733_032024-F.webp"}
        ]

    # 5️⃣ Limpieza por seguridad (sin nulos ni arrays vacíos)
    for k, v in list(item_api.items()):
        if v in [None, "", []]:
            if k not in ["sale_terms", "pictures"]:  # dejamos los requeridos
                item_api.pop(k, None)

                # --- Asegurar que las dimensiones de paquete estén presentes y no se borren ---
    for k in ["package_length", "package_width", "package_height", "package_weight"]:
        if not item_api.get(k) or item_api[k] == 0:
            # Intenta recuperar del 'matched' nuevamente
            dim_key = "SELLER_" + k.upper()
            val = (matched.get(dim_key) or {}).get("number")
            if val:
                item_api[k] = round(float(val), 2)
        # Valor por defecto mínimo (ML exige >0)
        if not item_api.get(k) or item_api[k] == 0:
            item_api[k] = 1.0 if "weight" not in k else 0.5

    # --- No eliminar campos numéricos aunque sean 0 ---
    for k, v in list(item_api.items()):
        if v in ["", None, []]:
            if k not in [
                "sale_terms", "pictures",
                "package_length", "package_width",
                "package_height", "package_weight"
            ]:
                item_api.pop(k, None)

    return {
        "asin": asin,
        "gtins": gtins,
        "seller_sku": asin,
        "category_id": category_id,
        "attributes": attrs,
        "title": title,
        "description": description,
        "prices": prices,
        "api_ready_item": item_api
    }


# ============================================================
# 🚀 CLI principal
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Uso: python3 transform_mapper_new.py <ruta_json_amazon>")
        sys.exit(1)

    arg_path = sys.argv[1]
    if not os.path.exists(arg_path):
        for base in ["outputs/json", "outputs"]:
            candidate = os.path.join(base, os.path.basename(arg_path))
            if os.path.exists(candidate):
                arg_path = candidate
                break
    if not os.path.exists(arg_path):
        print(f"❌ No se encontró el archivo: {arg_path}")
        sys.exit(1)

    amazon_json = load_json_file(arg_path)
    title = amazon_json.get("title") or amazon_json.get("product_title") or "Producto"
    match = match_category(title, amazon_json.get("asin", ""))
    cid = match["matched_category_id"] if match else "CBT1157"

    print("🚀 Construyendo atributos completos desde Amazon → ML …")
    result = build_meli_attributes(amazon_json, cid)

    out_folder = "logs/publish_ready"
    os.makedirs(out_folder, exist_ok=True)
    out_path = f"{out_folder}/{cid}_{os.path.basename(arg_path)}"
    save_json_file(out_path, result["api_ready_item"])

    print(f"\n✅ Guardado: {out_path}")
    print(json.dumps(result["api_ready_item"], indent=2, ensure_ascii=False))

    # ============================================================
# 🧩 Normalizador desde JSON CBT → formato /global/items
# ============================================================
def normalize_cbt_item(json_path: str) -> dict:
    """
    Corrige y normaliza un JSON descargado de /marketplace/items
    para hacerlo válido para el POST /global/items (Mercado Libre Global Selling).
    """
    import json

    with open(json_path, "r", encoding="utf-8") as fh:
        item = json.load(fh)

    body = {
        "title": ai_title_es[:60],
        "category_id": item.get("category_id", "CBT9999"),
        "currency_id": "USD",
        "available_quantity": 10,
        "condition": "new",
        "listing_type_id": "gold_pro",
        "buying_mode": "buy_it_now",
        "description": {"plain_text": ai_desc_es},
        "package_length": L,
        "package_width": W,
        "package_height": H,
        "package_weight": KG,
        "attributes": [],
        "sale_terms": item.get("sale_terms", [])
        "pictures": images,
        # Publicación con Net Proceeds (no enviar 'price')
        "global_net_proceeds": net_amount,
        # Auditoría opcional
        "_source_price": base_price,
        "_net_proceeds": net_amount,
        # SKU global
        "seller_custom_field": asin,
        # Marketplaces reales del vendedor
        "sites_to_sell": sites,
    }

    # --- Extraer dimensiones desde attributes ---
    attr_map = {a.get("id"): a for a in item.get("attributes", [])}

    def get_dim(attr_id):
        a = attr_map.get(attr_id)
        if a and a.get("value_struct"):
            return a["value_struct"]["number"]
        elif a and a.get("value_name"):
            try:
                return float(a["value_name"].split()[0])
            except Exception:
                return 0
        return 0

    body["package_length"] = get_dim("PACKAGE_LENGTH")
    body["package_width"]  = get_dim("PACKAGE_WIDTH")
    body["package_height"] = get_dim("PACKAGE_HEIGHT")
    body["package_weight"] = get_dim("PACKAGE_WEIGHT")

    # Mantener todos los attributes tal cual
    body["attributes"] = item.get("attributes", [])

    # --- Normalizar imágenes ---
    pics = []
    for pic in item.get("pictures", []):
        if "secure_url" in pic:
            pics.append({"source": pic["secure_url"]})
        elif "url" in pic:
            pics.append({"source": pic["url"]})
    body["pictures"] = pics

    # --- Asegurar marketplaces destino (sites_to_sell) ---
    body["sites_to_sell"] = [
        {"site_id": "MLM", "logistic_type": "remote", "title": body["title"]},
        {"site_id": "MLC", "logistic_type": "remote", "title": body["title"]},
        {"site_id": "MCO", "logistic_type": "remote", "title": body["title"]},
        {"site_id": "MLB", "logistic_type": "remote", "title": body["title"]},
        {"site_id": "MLA", "logistic_type": "remote", "title": body["title"]}
    ]

    return body


if __name__ == "__main__":
    main()