import os
import requests
from dotenv import load_dotenv

def refresh_amazon_token():
    """
    Renueva el access_token de Amazon SP-API usando el refresh_token guardado en .env.
    Luego actualiza automáticamente el archivo .env con los nuevos tokens.
    """

    print("🔄 Renovando access token de Amazon SP-API...")

    # Cargar variables actuales del archivo .env
    load_dotenv()

    client_id = os.getenv("AMZ_CLIENT_ID")
    client_secret = os.getenv("AMZ_CLIENT_SECRET")
    refresh_token = os.getenv("AMZ_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token]):
        print("❌ Error: faltan datos en el archivo .env (client_id, client_secret o refresh_token).")
        return

    url = "https://api.amazon.com/auth/o2/token"
    headers = {"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"}
    data = {
        "grant_type": "refresh_token",
        "refresh_token": refresh_token,
        "client_id": client_id,
        "client_secret": client_secret,
    }

    # Solicitar nuevo token
    r = requests.post(url, headers=headers, data=data)

    if r.status_code != 200:
        print(f"❌ Error al renovar token ({r.status_code}): {r.text}")
        return

    tokens = r.json()
    access_token = tokens.get("access_token")
    new_refresh_token = tokens.get("refresh_token")

    if not access_token:
        print("❌ No se recibió access_token en la respuesta.")
        print(r.text)
        return

    # Mostrar en consola
    print("✅ Token renovado correctamente.")
    print("🆕 Nuevo access_token:", access_token[:60] + "...")
    print("♻️ Nuevo refresh_token:", new_refresh_token[:60] + "...")

    # Actualizar el archivo .env automáticamente
    env_path = ".env"
    with open(env_path, "r") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        if line.startswith("AMZ_ACCESS_TOKEN="):
            new_lines.append(f"AMZ_ACCESS_TOKEN={access_token}\n")
        elif line.startswith("AMZ_REFRESH_TOKEN=") and new_refresh_token:
            new_lines.append(f"AMZ_REFRESH_TOKEN={new_refresh_token}\n")
        else:
            new_lines.append(line)

    with open(env_path, "w") as f:
        f.writelines(new_lines)

    print("💾 Archivo .env actualizado automáticamente.")

if __name__ == "__main__":
    refresh_amazon_token()