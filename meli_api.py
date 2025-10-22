import os, time, requests, random

if sys.prefix == sys.base_prefix:
    venv_python = os.path.join(os.path.dirname(__file__), "venv", "bin", "python")
    if os.path.exists(venv_python):
        print(f"⚙️ Activando entorno virtual automáticamente desde {venv_python}...")
        os.execv(venv_python, [venv_python] + sys.argv)
    else:
        print("⚠️ No se encontró el entorno virtual (venv). Créalo con: python3.11 -m venv venv")
        sys.exit(1)

ML_BASE = "https://api.mercadolibre.com"

def _headers():
    token = os.getenv("ML_ACCESS_TOKEN", "").strip()
    if not token:
        raise RuntimeError("Falta ML_ACCESS_TOKEN en .env")
    return {"Authorization": f"Bearer {token}"}

def _retryable_post(url, **kwargs):
    for attempt in range(1, 6):
        try:
            r = requests.post(url, timeout=90, **kwargs)
            if r.status_code in (429,) or 500 <= r.status_code < 600:
                raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
            return r
        except Exception as e:
            if attempt == 5:
                raise
            sleep_s = min(2 * attempt + random.random(), 10)
            print(f"[retry] intento {attempt} falló ({e}). Reintentando en {sleep_s:.1f}s…")
            time.sleep(sleep_s)

def upload_picture(image_url: str) -> str:
    img = requests.get(image_url, timeout=25)
    img.raise_for_status()
    files = {"file": (os.path.basename(image_url) or "image.jpg", img.content)}
    r = _retryable_post(f"{ML_BASE}/pictures/items/upload", headers=_headers(), files=files)
    r.raise_for_status()
    data = r.json()
    return data.get("id")

def create_global_item(body: dict) -> dict:
    headers = {**_headers(), "Content-Type": "application/json"}
    r = _retryable_post(f"{ML_BASE}/global/items", headers=headers, json=body)
    r.raise_for_status()
    return r.json()