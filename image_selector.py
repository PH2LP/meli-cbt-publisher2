import re
import requests
from difflib import SequenceMatcher

def _is_low_res(url: str) -> bool:
    """Detecta imágenes pequeñas como _SL75_ o _SX342_."""
    return any(x in url for x in ["_SL75_", "_SX342_", "_SX522_", "_SS100_", "_AC_UL75_", "_AC_SR75_"])

def _is_same_image(u1: str, u2: str) -> bool:
    """Evalúa si dos URLs son de la misma imagen base (solo cambia tamaño)."""
    base1 = re.sub(r"_[A-Z]{2}\d+_.*\.jpg$", "", u1)
    base2 = re.sub(r"_[A-Z]{2}\d+_.*\.jpg$", "", u2)
    return SequenceMatcher(None, base1, base2).ratio() > 0.9

def _validate_url(url: str) -> bool:
    """Chequea si la imagen existe y responde 200 OK."""
    try:
        r = requests.head(url, timeout=5)
        return r.status_code == 200
    except:
        return False

def select_best_images(image_list, max_images=10):
    """
    Toma todas las URLs de Amazon y devuelve una lista optimizada:
    - Elimina duplicados
    - Filtra baja resolución
    - Se queda con la mejor calidad (mayor tamaño)
    - Valida accesibilidad
    """
    if not image_list:
        return []

    clean = []
    for url in image_list:
        if not url or _is_low_res(url):
            continue
        if any(_is_same_image(url, existing) for existing in clean):
            continue
        if not _validate_url(url):
            continue
        clean.append(url)
        if len(clean) >= max_images:
            break

    return clean