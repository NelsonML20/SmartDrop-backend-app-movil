import os
import requests
from dotenv import load_dotenv

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

headers = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"
}

_session = requests.Session()
_session.headers.update(headers)

def supabase_get(tabla, filtros=None):
    url = f"{SUPABASE_URL}/rest/v1/{tabla}"
    if filtros:
        url += f"?{filtros}"
    response = _session.get(url)          
    print(f">>> URL: {url}")
    print(f">>> Status: {response.status_code}")
    print(f">>> Respuesta: {response.text}")
    return response.json()

def supabase_post(tabla, datos):
    url = f"{SUPABASE_URL}/rest/v1/{tabla}"
    response = _session.post(url, json=datos)
    print(f">>> POST URL: {url}")
    print(f">>> POST Status: {response.status_code}")
    print(f">>> POST Respuesta: {response.text}")
    return response

def supabase_patch(tabla, filtros, datos):
    url = f"{SUPABASE_URL}/rest/v1/{tabla}?{filtros}"
    response = _session.patch(url, json=datos)
    return response

def supabase_get(tabla, filtros=None):
    url = f"{SUPABASE_URL}/rest/v1/{tabla}"
    if filtros:
        url += f"?{filtros}"
    response = requests.get(url, headers=headers)
    print(f">>> URL: {url}")
    print(f">>> Status: {response.status_code}")
    print(f">>> Respuesta: {response.text}")
    return response.json()