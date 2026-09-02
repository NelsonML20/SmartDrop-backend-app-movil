# usuarios/vivienda_utils.py
from django.core.cache import cache
from smartdrop.supabase_client import supabase_get

TTL_CACHE_VIVIENDA = 600 


def resolver_vivienda_activa(id_usuario):
    clave = f"vivienda_activa:{id_usuario}"
    vivienda = cache.get(clave)
    if vivienda is not None:
        return vivienda

    resultado = supabase_get("vivienda", f"id_usuario_propietario=eq.{id_usuario}&select=*&limit=1")
    vivienda = resultado[0] if resultado else None
    if vivienda:
        cache.set(clave, vivienda, TTL_CACHE_VIVIENDA)
    return vivienda


def invalidar_cache_vivienda(id_usuario):
    cache.delete(f"vivienda_activa:{id_usuario}")