import os, json, requests, dotenv

dotenv_file = ".env"
dotenv.load_dotenv(dotenv_file)

client_id = os.getenv("ML_CLIENT_ID")
client_secret = os.getenv("ML_CLIENT_SECRET")
refresh_token = os.getenv("ML_REFRESH_TOKEN")

print("🔄 Renovando access token de Mercado Libre...")

url = "https://api.mercadolibre.com/oauth/token"
payload = {
    "grant_type": "refresh_token",
    "client_id": client_id,
    "client_secret": client_secret,
    "refresh_token": refresh_token
}

res = requests.post(url, data=payload)
data = res.json()

if "access_token" not in data:
    print("❌ Error al renovar token:", data)
    exit(1)

access_token = data["access_token"]
refresh_token_new = data["refresh_token"]

dotenv.set_key(dotenv_file, "ML_ACCESS_TOKEN", access_token)
dotenv.set_key(dotenv_file, "ML_REFRESH_TOKEN", refresh_token_new)

print("✅ Token renovado correctamente.")
print("🆕 Nuevo access_token:", access_token[:50] + "...")
print("♻️ Nuevo refresh_token:", refresh_token_new[:50] + "...")

# Exportar manualmente sin errores
export_cmds = [
    f'export ML_ACCESS_TOKEN="{access_token}"',
    f'export ML_REFRESH_TOKEN="{refresh_token_new}"'
]
for cmd in export_cmds:
    print(cmd)

print("⚡ Ejecutá manualmente los dos 'export' de arriba en tu terminal para activarlos.")