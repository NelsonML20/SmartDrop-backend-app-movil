from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .authentication import SupabaseJWTAuthentication
from .permissions import EsAdministrador
from smartdrop.supabase_client import supabase_get
from concurrent.futures import ThreadPoolExecutor
from .sensor_utils import resolver_sensor as _resolver_sensor
from django.core.cache import cache
import hashlib


PARAMETROS_VALIDOS = {"flujo", "presion", "nivel"}





def _serie_flujo_presion(sensor, desde, hasta):
    filtro = (
        f"id_sensor=eq.{sensor['id_sensor']}"
        f"&fecha_registro=gte.{desde}&fecha_registro=lte.{hasta}"
        f"&order=fecha_registro.asc&select=valor,fecha_registro"
    )
    lecturas = supabase_get("lectura", filtro)
    rango_min, rango_max = sensor.get("rango_min"), sensor.get("rango_max")

    datos = []
    for l in lecturas:
        valor = l["valor"]
        fuera_de_rango = (
            (rango_min is not None and valor < rango_min) or
            (rango_max is not None and valor > rango_max)
        )
        datos.append({"fecha": l["fecha_registro"], "valor": valor, "fuera_de_rango": fuera_de_rango})
    return datos

    """
    Se grafica porcentaje_llenado (ya calculado por la esp32).
    'Fuera de rango' se evalúa sobre nivel_cm crudo + la bandera es_valido
    que la esp32 ya determina
    """

def _serie_nivel(sensor_nivel, desde, hasta):

    filtro = (
        f"fecha_hora=gte.{desde}&fecha_hora=lte.{hasta}"
        f"&order=fecha_hora.asc&select=nivel_cm,porcentaje_llenado,fecha_hora,es_valido"
    )
    historial = supabase_get("historial_nivel_tanque", filtro)
    rango_min, rango_max = sensor_nivel.get("rango_min"), sensor_nivel.get("rango_max")

    datos = []
    for h in historial:
        nivel_cm = h["nivel_cm"]
        fuera_de_rango = (
            not h.get("es_valido", True) or
            (rango_min is not None and nivel_cm < rango_min) or
            (rango_max is not None and nivel_cm > rango_max)
        )
        datos.append({
            "fecha": h["fecha_hora"],
            "valor": h["porcentaje_llenado"],
            "fuera_de_rango": fuera_de_rango,
        })
    return datos


class GraficasView(APIView):

    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsAdministrador]

    def get(self, request):
        parametros = [p.strip() for p in request.query_params.get("parametros", "flujo").split(",") if p.strip()]

        invalidos = set(parametros) - PARAMETROS_VALIDOS
        if invalidos:
            return Response(
                {"error": f"Parámetros no válidos: {invalidos}. Usa: flujo, presion, nivel."},
                status=status.HTTP_400_BAD_REQUEST
            )

        hasta = request.query_params.get("hasta") or datetime.utcnow().isoformat()
        desde = request.query_params.get("desde") or (datetime.utcnow() - timedelta(days=1)).isoformat()

        # ── Caché adaptativo: rangos amplios cambian poco, se cachean más tiempo ──
        try:
            amplitud_dias = (datetime.fromisoformat(hasta) - datetime.fromisoformat(desde)).days
        except Exception:
            amplitud_dias = 1

        if amplitud_dias <= 1:
            ttl_bucket = 10
        elif amplitud_dias <= 7:
            ttl_bucket = 30
        else:
            ttl_bucket = 60

        try:
            hasta_epoch = int(datetime.fromisoformat(hasta).timestamp())
            hasta_bucket = hasta_epoch - (hasta_epoch % ttl_bucket)
        except Exception:
            hasta_bucket = 0

        clave_cache = hashlib.md5(
            f"graficas:{','.join(sorted(parametros))}:{desde}:{hasta_bucket}".encode()
        ).hexdigest()

        cacheado = cache.get(clave_cache)
        if cacheado is not None:
            return Response(cacheado, status=status.HTTP_200_OK)

        resultado = {}
        for parametro in parametros:
            sensor = _resolver_sensor(parametro)
            if not sensor:
                resultado[parametro] = {"error": "Sensor no configurado."}
                continue

            if parametro == "nivel":
                datos, unidad = _serie_nivel(sensor, desde, hasta), "%"
            else:
                datos, unidad = _serie_flujo_presion(sensor, desde, hasta), sensor["unidad_medida"]

            resultado[parametro] = {
                "unidad": unidad,
                "rango_min": sensor.get("rango_min"),
                "rango_max": sensor.get("rango_max"),
                "datos": datos,
            }

        cache.set(clave_cache, resultado, ttl_bucket)
        return Response(resultado, status=status.HTTP_200_OK)


class ResumenDashboardView(APIView):
   
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsAdministrador]

    def get(self, request):
        with ThreadPoolExecutor(max_workers=3) as executor:
            future_flujo = executor.submit(self._obtener_ultimo, "flujo")
            future_presion = executor.submit(self._obtener_ultimo, "presion")
            future_nivel = executor.submit(self._obtener_nivel)

            flujo_data = future_flujo.result()
            presion_data = future_presion.result()
            nivel_data = future_nivel.result()

        resumen = {}
        total_alertas = 0

        for clave, dato in [("flujo", flujo_data), ("presion", presion_data)]:
            if dato is None:
                continue
            if dato["fuera_de_rango"]:
                total_alertas += 1
            resumen[clave] = dato

        if nivel_data is not None:
            if nivel_data["fuera_de_rango"]:
                total_alertas += 1
            resumen["nivel"] = nivel_data

        resumen["total_alertas"] = total_alertas
        return Response(resumen, status=status.HTTP_200_OK)

    def _obtener_ultimo(self, parametro):
        sensor = _resolver_sensor(parametro)
        if not sensor:
            return None
        ultima = supabase_get(
            "lectura",
            f"id_sensor=eq.{sensor['id_sensor']}&order=fecha_registro.desc&limit=1&select=valor,fecha_registro"
        )
        if not ultima:
            return None
        valor = ultima[0]["valor"]
        rango_min, rango_max = sensor.get("rango_min"), sensor.get("rango_max")
        fuera_de_rango = (rango_min is not None and valor < rango_min) or (rango_max is not None and valor > rango_max)
        return {
            "valor": valor, "unidad": sensor["unidad_medida"],
            "fecha": ultima[0]["fecha_registro"], "fuera_de_rango": fuera_de_rango,
        }

    def _obtener_nivel(self):
        ultimo_nivel = supabase_get(
            "historial_nivel_tanque",
            "order=fecha_hora.desc&limit=1&select=porcentaje_llenado,fecha_hora,nivel_cm,es_valido"
        )
        if not ultimo_nivel:
            return None
        sensor_nivel = _resolver_sensor("nivel")
        nivel_cm = ultimo_nivel[0]["nivel_cm"]
        rango_min = sensor_nivel.get("rango_min") if sensor_nivel else None
        rango_max = sensor_nivel.get("rango_max") if sensor_nivel else None
        fuera_de_rango = (
            not ultimo_nivel[0].get("es_valido", True)
            or (rango_min is not None and nivel_cm < rango_min)
            or (rango_max is not None and nivel_cm > rango_max)
        )
        return {
            "valor": ultimo_nivel[0]["porcentaje_llenado"], "unidad": "%",
            "fecha": ultimo_nivel[0]["fecha_hora"], "fuera_de_rango": fuera_de_rango,
        }

        resumen["total_alertas"] = total_alertas
        return Response(resumen, status=status.HTTP_200_OK)