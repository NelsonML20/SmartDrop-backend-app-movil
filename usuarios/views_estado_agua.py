from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .authentication import SupabaseJWTAuthentication
from .permissions import EsUsuarioAutenticado
from concurrent.futures import ThreadPoolExecutor
from django.core.cache import cache
from .vivienda_utils import resolver_vivienda_activa as _resolver_vivienda_activa
from smartdrop.supabase_client import supabase_get
from .views_dashboard import _resolver_sensor
from .consumo_utils import calcular_consumo_rango
from .sensor_utils import resolver_sensor as _resolver_sensor, resolver_tanque_por_sensor_nivel, resolver_tanque


LITROS_POR_BARRIL = 158.987  





def _armar_presion(id_vivienda):
    sensor = _resolver_sensor("presion")
    if not sensor:
        return None

    ultima = supabase_get(
        "lectura",
        f"id_sensor=eq.{sensor['id_sensor']}&id_vivienda=eq.{id_vivienda}"
        f"&order=fecha_registro.desc&limit=1&select=valor,fecha_registro"
    )
    if not ultima:
        return None

    valor = ultima[0]["valor"]
    umbral_bajo = sensor.get("umbral_critico_bajo")
    umbral_alto = sensor.get("umbral_critico_alto")

    if umbral_bajo is not None and valor < umbral_bajo:
        estado, descripcion, color = "Baja", "Problema en la presión del agua. Se recomienda revisar el suministro.", "rojo"
    elif umbral_alto is not None and valor > umbral_alto:
        estado, descripcion, color = "Alta", "Problema en la presión del agua. Se recomienda revisar el suministro.", "rojo"
    else:
        estado, descripcion, color = "Normal", "La presión es adecuada para el uso de duchas y lavadoras.", "verde"

    return {
        "valor": valor,
        "unidad": sensor["unidad_medida"], 
        "estado": estado,
        "descripcion": descripcion,
        "color": color,
        "fecha": ultima[0]["fecha_registro"],
    }


def _armar_calidad(id_vivienda):
    sensor = _resolver_sensor("calidad")
    if not sensor:
        return None

    ultima = supabase_get(
        "lectura",
        f"id_sensor=eq.{sensor['id_sensor']}&id_vivienda=eq.{id_vivienda}"
        f"&order=fecha_registro.desc&limit=1&select=valor,fecha_registro"
    )
    if not ultima:
        return None

    valor = ultima[0]["valor"]

    
    if valor <= 100:
        estrellas, estado, descripcion, color = 5, "¡AGUA SEGURA!", "Se puede tomar agua con seguridad.", "verde"
    elif valor <= 200:
        estrellas, estado, descripcion, color = 4, "¡AGUA SEGURA!", "Calidad muy buena, apta para consumo.", "verde"
    elif valor <= 300:
        estrellas, estado, descripcion, color = 3, "ACEPTABLE", "Calidad aceptable, se recomienda monitoreo continuo.", "amarillo"
    else:
        estrellas, estado, descripcion, color = 2, "CALIDAD DE AGUA BAJA", "Calidad de agua baja, revisar. Se recomienda análisis adicional.", "rojo"

    clave_cache = f"incidentes_calidad:{sensor['id_sensor']}"
    total = cache.get(clave_cache)
    if total is None:
        hace_30_dias = (datetime.utcnow() - timedelta(days=30)).isoformat()
        incidentes = supabase_get(
            "incidente_calidad",
            f"id_sensor_tds=eq.{sensor['id_sensor']}&fecha_deteccion=gte.{hace_30_dias}&select=id_incidente"
        )
        total = len(incidentes) if incidentes else 0
        cache.set(clave_cache, total, 60) 


    texto_anomalias = (
        "No se han detectado anomalías en los últimos 30 días" if total == 0
        else f"Se detectaron {total} anomalía(s) en los últimos 30 días"
    )

    return {
        "valor_ppm": valor,
        "estrellas": estrellas,
        "estado": estado,
        "descripcion": descripcion,
        "color": color,
        "texto_anomalias": texto_anomalias,
        "fecha": ultima[0]["fecha_registro"],
    }

def _estado_nivel(porcentaje):
    
    if porcentaje < 15:
        return "Crítico", "Nivel de agua bajo, usa el agua con precaución.", "rojo"
    elif porcentaje < 30:
        return "Moderado", "El nivel del tanque está bajando, considera moderar tu consumo.", "amarillo"
    else:
        return "Adecuado", "El nivel de agua es adecuado.", "verde"


def _armar_nivel(id_tanque):
    tanque = resolver_tanque(id_tanque)
    if not tanque:
      return None
    

    ultimo = supabase_get(
        "historial_nivel_tanque",
        f"id_tanque=eq.{id_tanque}&order=fecha_hora.desc&limit=1"
        f"&select=porcentaje_llenado,nivel_cm,fecha_hora"
    )
    if not ultimo:
        return None
    ultimo = ultimo[0]

    porcentaje = ultimo["porcentaje_llenado"] or 0.0
    capacidad_max_litros = tanque["capacidad_maxima_litros"]

    litros_disponibles = round(capacidad_max_litros * (porcentaje / 100.0), 1)

    estado, descripcion, color = _estado_nivel(porcentaje)

    return {
        "porcentaje": porcentaje,
        "litros_disponibles": litros_disponibles,
        "capacidad_maxima_litros": capacidad_max_litros,
        "barriles_disponibles": round(litros_disponibles / LITROS_POR_BARRIL, 2),
        "capacidad_maxima_barriles": round(capacidad_max_litros / LITROS_POR_BARRIL, 2),
        "fecha": ultimo["fecha_hora"],
        "estado": estado,
        "descripcion": descripcion,
        "color": color,
        "bomba_estado": None,
        "autonomia_estimada_texto": None,
    }

def _armar_consumo_hoy(id_vivienda):
    """Versión ligera solo para el Home: litros consumidos en lo que va del día."""
    hoy = datetime.utcnow().date()
    inicio = datetime.combine(hoy, datetime.min.time())
    total = calcular_consumo_rango(id_vivienda, inicio, datetime.utcnow())
    return {"litros_hoy": round(total, 2)}


class EstadoAguaView(APIView):
    
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsUsuarioAutenticado]

    def get(self, request):
        vivienda = _resolver_vivienda_activa(request.user.id_usuario)
        if not vivienda:
            return Response({"error": "No tienes una vivienda vinculada."}, status=status.HTTP_404_NOT_FOUND)

        id_vivienda = vivienda["id_vivienda"]

        
        sensor_nivel = _resolver_sensor("nivel")
        id_tanque = resolver_tanque_por_sensor_nivel(sensor_nivel["id_sensor"]) if sensor_nivel else None

        # Presión, Calidad y Nivel no dependen entre sí 
        with ThreadPoolExecutor(max_workers=4) as executor:
            future_presion = executor.submit(_armar_presion, id_vivienda)
            future_calidad = executor.submit(_armar_calidad, id_vivienda)
            future_nivel = executor.submit(_armar_nivel, id_tanque) if id_tanque else None
            future_consumo = executor.submit(_armar_consumo_hoy, id_vivienda)


            presion_data = future_presion.result()
            calidad_data = future_calidad.result()
            nivel_data = future_nivel.result() if future_nivel else None
            consumo_data = future_consumo.result()

        severidad = {"rojo": 2, "amarillo": 1, "verde": 0}
        partes = [d for d in [presion_data, calidad_data, nivel_data] if d is not None]

        if not partes:
            resumen_general = {"mensaje": "Aún no hay datos disponibles.", "color": "verde"}
        else:
            peor = max(partes, key=lambda d: severidad.get(d.get("color", "verde"), 0))
            if severidad.get(peor.get("color"), 0) == 0:
                resumen_general = {"mensaje": "Agua segura, todo funciona con normalidad.", "color": "verde"}
            else:
                resumen_general = {
                    "mensaje": peor.get("mensaje") or peor.get("descripcion"),
                    "color": peor.get("color"),
                }

        return Response({
            "vivienda": {"id_vivienda": id_vivienda, "direccion": vivienda.get("direccion")},
            "resumen_general": resumen_general,
            "presion": presion_data,
            "calidad": calidad_data,
            "nivel": nivel_data,
            "consumo": consumo_data,
        }, status=status.HTTP_200_OK)