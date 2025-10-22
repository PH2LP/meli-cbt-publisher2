#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# ============================================================
# 🧠 transform_mapper.py (v2.6 FULL AUTO + SMART PACKAGE FIX)
# Amazon → MercadoLibre attribute translator
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

from openai import OpenAI
client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None

API = "https://api.mercadolibre.com"
HEADERS = {"Authorization": f"Bearer {ML_ACCESS_TOKEN}"} if ML_ACCESS_TOKEN else {}

CACHE_PATH = "logs/ai_equivalences_cache.json"

# === NUEVO: caches ligeros para ahorrar tokens título/descr ===
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

# === NUEVO: normalización de unidades ===
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
    # fallback sin conversión conocida
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
# 🔍 Categoría automática
# ============================================================
def improve_title_with_ai(title, brand=None, model=None):
    if not client:
        return title
    try:
        prompt = f"""
Eres experto en comercio electrónico. Devuelve este título limpio en español LATAM:
1. Mantén marca y modelo si existen.
2. Sin emojis ni HTML.
Título: {title}
Marca: {brand or ''}
Modelo: {model or ''}
"""
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            temperature=0.3,
            messages=[{"role":"user","content":prompt}],
        )
        return resp.choices[0].message.content.strip()[:80]
    except Exception:
        return title

def predict_category(title, amazon_json):
    improved = improve_title_with_ai(title, amazon_json.get("brand"), amazon_json.get("model"))
    q = " ".join(filter(None, [improved, amazon_json.get("brand"), amazon_json.get("model"),
                               amazon_json.get("color"), amazon_json.get("material")]))
    for site in ["CBT","MLM","MLC","MLB","MCO"]:
        try:
            r = requests.get(f"{API}/sites/{site}/domain_discovery/search",
                             params={"q": q}, headers=HEADERS, timeout=10)
            if r.ok and isinstance(r.json(), list) and r.json():
                cid = r.json()[0].get("category_id")
                cname = r.json()[0].get("category_name")
                if cid:
                    print(f"🧭 Categoría detectada ({site}): {cid} → {cname}")
                    return cid
        except Exception as e:
            print(f"⚠️ {site} falló: {e}")
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
        "item_package_dimensions.length", "package_dimensions.length", "item_package_length",
        "package_length", "shipping_dimensions.length", "shipping_length", "outer_dimensions.length",
        "outer_carton_dimensions.length", "outer_package_length", "box_length", "parcel_length"
    ],
    "width": [
        "item_package_dimensions.width", "package_dimensions.width", "item_package_width",
        "package_width", "shipping_dimensions.width", "shipping_width", "outer_dimensions.width",
        "outer_carton_dimensions.width", "outer_package_width", "box_width", "parcel_width"
    ],
    "height": [
        "item_package_dimensions.height", "package_dimensions.height", "item_package_height",
        "package_height", "shipping_dimensions.height", "shipping_height", "outer_dimensions.height",
        "outer_carton_dimensions.height", "outer_package_height", "box_height", "parcel_height"
    ],
    "weight": [
        "item_package_weight", "package_weight", "shipping_weight", "package_dimensions.weight",
        "item_package_dimensions.weight", "outer_package_weight", "carton_weight",
        "gross_weight", "boxed_weight", "parcel_weight"
    ]
}

# ============================================================
# 📦 Extraer dimensiones del PAQUETE (solo paquete) - Mejorado
# ============================================================
def get_package_dimension(flat, kind):
    kind = kind.lower()
    norm_flat = {normalize_key(k): v for k, v in flat.items()}
    candidates = []

    # 1️⃣ Buscar rutas típicas de Amazon (nested)
    for prefix in ["package_dimensions", "item_package_dimensions", "shipping_dimensions", "outer_package_dimensions"]:
        value_key = normalize_key(f"{prefix}.{kind}.value")
        unit_key  = normalize_key(f"{prefix}.{kind}.unit")

        # Buscar coincidencia exacta
        val = next((v for fk, v in norm_flat.items() if value_key in fk), None)
        unit = next((v for fk, v in norm_flat.items() if unit_key in fk), None)

        if val:
            num = extract_number(val)
            if num is not None:
                if unit and unit.lower().startswith("in"):  # convertir pulgadas a cm
                    num *= 2.54
                    unit = "cm"
                elif unit and unit.lower().startswith("pound"):
                    num *= 0.453592
                    unit = "kg"
                elif not unit:
                    unit = "cm" if kind != "weight" else "kg"
                return {"number": round(num, 3), "unit": unit}

    # 2️⃣ Buscar coincidencia genérica si no se encontró en formato estructurado
    for fk, v in norm_flat.items():
        if kind in fk and any(x in fk for x in ["package", "shipping", "outer", "carton"]):
            num = extract_number(v)
            if num is not None:
                unit = "cm" if kind != "weight" else "kg"
                return {"number": num, "unit": unit}

    print(f"⚠️ No se encontró {kind} del paquete en el JSON (ni valor ni unidad).")
    return None


# ============================================================
# 🧩 Diccionario base (inicial)
# ============================================================
BASE_EQUIV = {
    "BRAND":["brand","manufacturer","brand_name"],
    "MODEL":["model","model_number","item_model_number"],
    "COLOR":["color","color_name"],
    "MATERIAL":["material","materials"],
    "TOY_MATERIALS":["material","materials"],
    "PIECES_NUMBER":["number_of_pieces","numberOfPieces"],
    "WEIGHT":["weight","item_weight","shipping_weight"],
    "HEIGHT":["height","item_height","dimensions.height"],
    "WIDTH":["width","item_width","dimensions.width"],
    "LENGTH":["length","item_length","dimensions.length"],
    "CATALOG_TITLE":["title","product_title"],
    "RECOMMENDED_AGE_GROUP":["age_range","recommended_age","ageRange"],
}

# ============================================================
# 🧠 Cache persistente (aprendizaje)
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
# 🤖 IA para equivalencias nuevas (mejorado)
# ============================================================
def ask_gpt_equivalences(category_id, missing, flat, cache):
    if not client:
        return {}
    # Evita volver a consultar por los que ya están en cache
    new_missing = [m for m in missing if m not in cache.keys()]
    if not new_missing:
        print("♻️ Todos los atributos faltantes ya están en cache, no se consulta IA.")
        return {}

    summary = "\n".join(f"{k}: {v}" for k,v in list(flat.items())[:200])
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

# === NUEVO: IA título + descripción con cache por ASIN ===
def generate_ai_title(asin: str, amazon_json: dict, max_chars=60)->str:
    if not client:
        return amazon_json.get("item_name") or amazon_json.get("title") or "Producto"
    cache = _load_small_cache(TITLE_CACHE_PATH)
    if asin and asin in cache:
        return cache[asin]
    # resumen pequeño para ahorrar tokens
    brand = _first(amazon_json, ["brandName","brand","attributes.brand[0].value","summaries[0].brandName"])
    model = _first(amazon_json, ["model_name","model_number","model","summaries[0].modelNumber"])
    raw_title = amazon_json.get("item_name") or amazon_json.get("title") or ""
    bullets = _list_from(amazon_json, ["attributes.bullet_point","bullet_point"])
    prompt = f"""Eres copywriter e-commerce LATAM. Crea un título de máx {max_chars} caracteres, claro y vendedor, usando marca y modelo si existen. Sin emojis ni símbolos raros.
Base:
- Título base: {raw_title}
- Marca: {brand}
- Modelo: {model}
- Bullets: {bullets[:3]}"""
    try:
        r = client.chat.completions.create(
            model=OPENAI_MODEL, temperature=0.3,
            messages=[{"role":"user","content":prompt}],
        )
        title = r.choices[0].message.content.strip()
        title = title[:max_chars]
        if asin:
            cache[asin]=title
            _save_small_cache(TITLE_CACHE_PATH, cache)
        return title
    except:
        return (raw_title or "Producto")[:max_chars]

def generate_ai_description(asin: str, amazon_json: dict)->str:
    if not client:
        return ""
    cache = _load_small_cache(DESC_CACHE_PATH)
    if asin and asin in cache:
        return cache[asin]
    brand = _first(amazon_json, ["brandName","brand","attributes.brand[0].value","summaries[0].brandName"])
    model = _first(amazon_json, ["model_name","model_number","model","summaries[0].modelNumber"])
    pieces = _first(amazon_json, ["number_of_pieces","attributes.number_of_pieces[0].value"])
    color = _first(amazon_json, ["color","attributes.color[0].value"])
    material = _first(amazon_json, ["material","attributes.material[0].value"])
    bullets = _list_from(amazon_json, ["attributes.bullet_point","bullet_point"])
    dims_pkg = _dims_hint(amazon_json)
    prompt = f"""Redacta una descripción larga (mínimo 3 párrafos) en español LATAM, persuasiva y clara, para Mercado Libre. Incluye beneficios y detalles clave. Evita promesas engañosas. Sin HTML, solo texto plano.
Datos:
- Marca: {brand} | Modelo: {model} | Piezas: {pieces}
- Color: {color} | Material: {material}
- Bullets: {bullets[:6]}
- Pista dimensiones paquete: {dims_pkg}
Cierra con llamado a la acción suave."""
    try:
        r = client.chat_completions.create(
            model=OPENAI_MODEL, temperature=0.4,
            messages=[{"role":"user","content":prompt}],
        )
    except AttributeError:
        # compat openai>=1.0
        r = client.chat.completions.create(
            model=OPENAI_MODEL, temperature=0.4,
            messages=[{"role":"user","content":prompt}],
        )
    desc = r.choices[0].message.content.strip()
    if asin:
        cache[asin]=desc
        _save_small_cache(DESC_CACHE_PATH, cache)
    return desc

def _first(data, paths):
    flat = flatten_summary(data)
    for p in paths:
        # intentar variantes con .value
        for k,v in flat.items():
            if p in k:
                return v
    return None

def _list_from(data, paths):
    flat = flatten_summary(data)
    out=[]
    for p in paths:
        for k,v in flat.items():
            if p in k:
                out.append(v)
    return out

def _dims_hint(data):
    flat=flatten_summary(data)
    for k,v in flat.items():
        if "item_package_dimensions" in k or "package_dimensions" in k:
            return f"{k}:{v}"
    return ""

# ============================================================
# 🏗️ Construir atributos ML (con reuso de cache)
# ============================================================
def build_meli_attributes(amazon_json, category_id):
    schema = get_category_schema(category_id)
    flat = flatten_summary(amazon_json)
    cache = load_cache()

    matched, missing = {}, []
    reused = 0

    # === NUEVO: ASIN y GTIN
    asin = amazon_json.get("asin") or _infer_asin_from_flat(flat)
    if asin:
        matched["SELLER_SKU"] = asin  # SKU del seller = ASIN

    gtins = _extract_gtins(flat)
    if gtins:
        matched["GTIN"] = gtins[0]  # si hay varios, usamos el primero (ML acepta uno)

    for aid, meta in schema.items():
        if aid in {"GTIN"} or aid.startswith("PACKAGE_"):
            # GTIN ya lo cargamos arriba; y no usamos PACKAGE_* atributos deprecated
            pass

        # --- Detectar dimensiones del paquete ---
        if aid in {"SELLER_PACKAGE_LENGTH", "SELLER_PACKAGE_WIDTH", "SELLER_PACKAGE_HEIGHT", "SELLER_PACKAGE_WEIGHT"}:
            dim = get_package_dimension(flat, aid.split("_")[-1].lower())
            if dim:
                matched[aid] = dim
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
            print(f"🤖 Pidiendo equivalencias IA solo para {len(new_to_ask)} nuevas...")
            new_eq = ask_gpt_equivalences(category_id, new_to_ask, flat, cache)
            for k,v in new_eq.items():
                val = find_value(flat, v)
                if val:
                    matched[k] = val

    # Mostrar dimensiones detectadas (solo si están todas)
    pkg_l = (matched.get("SELLER_PACKAGE_LENGTH") or {}).get("number")
    pkg_w = (matched.get("SELLER_PACKAGE_WIDTH") or {}).get("number")
    pkg_h = (matched.get("SELLER_PACKAGE_HEIGHT") or {}).get("number")
    pkg_wt= (matched.get("SELLER_PACKAGE_WEIGHT") or {}).get("number")
    if all([pkg_l is not None, pkg_w is not None, pkg_h is not None, pkg_wt is not None]):
        print(f"📦 Dimensiones del paquete detectadas → {pkg_w:.2f}×{pkg_l:.2f}×{pkg_h:.2f} cm – {pkg_wt:.3f} kg")

    # armar atributos finales
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
            # convertir a cm/kg si corresponde
            if "WEIGHT" in aid:
                num = _to_kg(num, u)
                u = "kg"
            elif aid.endswith(("LENGTH","WIDTH","HEIGHT")):
                num = _to_cm(num, u)
                u = "cm"
            if num is not None:a["value_struct"]={"number":float(num),"unit":u}
        elif vtype=="list":
            lower=str(val).lower()
            if lower in meta.get("values",{}):
                a["value_id"]=meta["values"][lower]
            else:a["value_name"]=val
        else:
            a["value_name"]=val
        attrs.append(a)

    total_schema=len(schema)
    filled=len(matched)
    print(f"\n📊 Resumen final → Amazon direct: {filled-reused}, IA cache: {reused}, Missing: {total_schema-filled}")

    # === NUEVO: título + descripción IA con cache
    title = generate_ai_title(asin or "", amazon_json, max_chars=60)
    description = generate_ai_description(asin or "", amazon_json)

    # Devolvemos info adicional para export
    return {
        "attributes":attrs,
        "schema": schema,
        "asin": asin,
        "gtins": gtins,
        "seller_sku": asin,
        "category_id": category_id,
        "title": title,
        "description": description
    }

# === NUEVO: helpers GTIN/ASIN ===
def _extract_gtins(flat: dict)->List[str]:
    gtins=[]
    # Amazon JSON típico: attributes.externally_assigned_product_identifier[*].value + .type
    for k,v in flat.items():
        if "externally_assigned_product_identifier" in k and k.endswith(".value"):
            val = re.sub(r"\D","",str(v))
            if val and 8 <= len(val) <= 14:
                gtins.append(val)
    # evitar duplicados preservando orden
    seen=set(); out=[]
    for g in gtins:
        if g not in seen:
            out.append(g); seen.add(g)
    return out

def _infer_asin_from_flat(flat: dict)->str|None:
    for k,v in flat.items():
        if k.endswith(".asin") or k.endswith(".ASIN") or k == "asin":
            return str(v).strip()
    return None

# ============================================================
# 🚀 CLI principal
# ============================================================
def main():
    if len(sys.argv) < 2:
        print("Uso: python3 transform_mapper_v2.6.py <ruta_json_amazon>")
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
    cid = predict_category(title, amazon_json)
    print("🚀 Construyendo atributos completos desde Amazon → ML ...")
    result = build_meli_attributes(amazon_json, cid)
    print(f"\n✅ Total atributos generados: {len(result['attributes'])}")
    out = f"logs/filled_attrs/{cid}_{os.path.basename(arg_path)}"
    save_json_file(out, result)  # guardamos TODO (attrs + title + desc + asin + gtins)
    print(f"💾 Guardado: {out}")
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    main()