from django.core.cache import cache
from smartdrop.supabase_client import supabase_get

TTL_CACHE_SENSOR = 300  
TTL_CACHE_TANQUE = 300


def resolver_sensor(tipo_sensor):
    clave = f"sensor:{tipo_sensor}"
    sensor = cache.get(clave)
    if sensor is not None:
        return sensor

    resultado = supabase_get("sensor", f"tipo_sensor=eq.{tipo_sensor}&select=*")
    sensor = resultado[0] if resultado else None
    if sensor:
        cache.set(clave, sensor, TTL_CACHE_SENSOR)
    return sensor


def resolver_tanque_por_sensor_nivel(id_sensor_nivel):
    clave = f"tanque:por_sensor:{id_sensor_nivel}"
    id_tanque = cache.get(clave)
    if id_tanque is not None:
        return id_tanque

    resultado = supabase_get("tanque", f"id_sensor_nivel=eq.{id_sensor_nivel}&select=id_tanque")
    id_tanque = resultado[0]["id_tanque"] if resultado else None
    if id_tanque is not None:
        cache.set(clave, id_tanque, TTL_CACHE_TANQUE)
    return id_tanque


def resolver_tanque(id_tanque):
    clave = f"tanque:{id_tanque}"
    tanque = cache.get(clave)
    if tanque is not None:
        return tanque

    resultado = supabase_get("tanque", f"id_tanque=eq.{id_tanque}&select=*")
    tanque = resultado[0] if resultado else None
    if tanque:
        cache.set(clave, tanque, TTL_CACHE_TANQUE)
    return tanque