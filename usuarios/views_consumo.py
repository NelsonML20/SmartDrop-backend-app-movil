from datetime import datetime, timedelta
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .authentication import SupabaseJWTAuthentication
from .permissions import EsUsuarioAutenticado
from smartdrop.supabase_client import supabase_get, supabase_post
from .vivienda_utils import resolver_vivienda_activa as _resolver_vivienda_activa
from .views_vivienda import supabase_get as _sg  
from .consumo_utils import calcular_consumo_rango, obtener_consumo_dia, serie_por_dia, serie_por_hora_hoy, total_consumo_dias, resolver_sensor, _calcular_dias_cerrados_batch


def _estado_consumo(consumo_total, porcentaje_cambio):
    if consumo_total <= 0:
        return "SIN ACTIVIDAD REGISTRADA", "gris"
    if porcentaje_cambio is None:
        return "CONSUMO REGISTRADO", "gris"
    if porcentaje_cambio > 25:
        return "CONSUMO ELEVADO", "rojo"
    if porcentaje_cambio > 10:
        return "CONSUMO LIGERAMENTE ELEVADO", "amarillo"
    if porcentaje_cambio < -10:
        return "CONSUMO REDUCIDO", "verde"
    return "CONSUMO NORMAL", "verde"


class ConsumoView(APIView):
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsUsuarioAutenticado]

    def get(self, request):
        vivienda = _resolver_vivienda_activa(request.user.id_usuario)
        if not vivienda:
            return Response({"error": "No tienes una vivienda vinculada."}, status=status.HTTP_404_NOT_FOUND)
        id_vivienda = vivienda["id_vivienda"]

        periodo = request.query_params.get("periodo", "dia")
        if periodo not in ("dia", "semana", "mes"):
            return Response({"error": "periodo inválido, usa dia, semana o mes."}, status=status.HTTP_400_BAD_REQUEST)

        hoy = datetime.utcnow().date()

        if periodo == "dia":
            serie = serie_por_hora_hoy(id_vivienda)
            consumo_total = round(sum(p["litros"] for p in serie), 2)
            consumo_anterior = obtener_consumo_dia(id_vivienda, hoy - timedelta(days=1))
            etiqueta = "día anterior"

        elif periodo == "semana":
            serie = serie_por_dia(id_vivienda, 7)
            consumo_total = round(sum(p["litros"] for p in serie), 2)
            inicio_pasada = hoy - timedelta(days=13)
            dias_semana_pasada = [inicio_pasada + timedelta(days=i) for i in range(7)]
            consumo_anterior = total_consumo_dias(id_vivienda, dias_semana_pasada)
            etiqueta = "semana pasada"

        else:
            serie = serie_por_dia(id_vivienda, 30)
            consumo_total = round(sum(p["litros"] for p in serie), 2)
            inicio_pasado = hoy - timedelta(days=59)
            dias_mes_pasado = [inicio_pasado + timedelta(days=i) for i in range(30)]
            consumo_anterior = total_consumo_dias(id_vivienda, dias_mes_pasado)
            etiqueta = "mes pasado"

        porcentaje = round(((consumo_total - consumo_anterior) / consumo_anterior) * 100, 1) if consumo_anterior else None
        estado_texto, color = _estado_consumo(consumo_total, porcentaje)

        texto_comparacion = (
            f"{'+' if porcentaje >= 0 else ''}{porcentaje}% vs. {etiqueta}"
            if porcentaje is not None else "Sin datos suficientes para comparar todavía."
        )
        punto_maximo = max(serie, key=lambda p: p["litros"]) if serie else None

        return Response({
            "periodo": periodo,
            "unidad": "L",
            "consumo_total": consumo_total,
            "estado_texto": estado_texto,
            "color": color,
            "comparacion": {"porcentaje": porcentaje, "texto": texto_comparacion},
            "serie": serie,
            "punto_maximo": punto_maximo,
        }, status=status.HTTP_200_OK)


class RetroalimentacionView(APIView):
    """GET /auth/retroalimentacion/ — Escenarios 2, 3, 4, 5 de PB044"""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsUsuarioAutenticado]

    def get(self, request):
        vivienda = _resolver_vivienda_activa(request.user.id_usuario)
        if not vivienda:
            return Response({"error": "No tienes una vivienda vinculada."}, status=status.HTTP_404_NOT_FOUND)
        id_vivienda = vivienda["id_vivienda"]

        hoy = datetime.utcnow().date()
        consumo_hoy = calcular_consumo_rango(id_vivienda, datetime.combine(hoy, datetime.min.time()), datetime.utcnow())

        fechas_previas = [hoy - timedelta(days=i) for i in range(1, 8)]
        valores_previos = _calcular_dias_cerrados_batch(id_vivienda, fechas_previas)
        dias_previos = [valores_previos[f.isoformat()] for f in fechas_previas]
        dias_validos = [d for d in dias_previos if d and d > 0]
        promedio_habitual = round(sum(dias_validos) / len(dias_validos), 2) if dias_validos else None

        razon = (consumo_hoy / promedio_habitual) if promedio_habitual else None

        if razon is None:
            estado, color = "normal", "verde"
        elif razon > 1.3:
            estado, color = "elevado", "rojo"
        elif razon < 0.7:
            estado, color = "bajo", "verde"
        else:
            estado, color = "normal", "verde"

        if estado == "elevado":
            mensaje, tipo_mensaje = "Consumo elevado de agua. Intenta reducir el uso en duchas y grifos abiertos.", "alerta_consumo"
        elif estado == "bajo":
            mensaje, tipo_mensaje = "¡Buen trabajo ahorrando agua!", "motivacional_positivo"
        else:
            mensaje, tipo_mensaje = "Tu consumo está dentro de lo normal. ¡Sigue así!", "motivacional_neutral"

        # Comparación 
        inicio_mes = hoy.replace(day=1)
        dias_transcurridos = (hoy - inicio_mes).days + 1

        fechas_mes_actual_cerradas = [inicio_mes + timedelta(days=i) for i in range(dias_transcurridos - 1)]
        consumo_mes_actual = total_consumo_dias(id_vivienda, fechas_mes_actual_cerradas) + calcular_consumo_rango(
            id_vivienda, datetime.combine(hoy, datetime.min.time()), datetime.utcnow()
        )

        primer_dia_mes_pasado = (inicio_mes - timedelta(days=1)).replace(day=1)
        fechas_mes_pasado = [primer_dia_mes_pasado + timedelta(days=i) for i in range(dias_transcurridos)]
        consumo_mes_pasado = total_consumo_dias(id_vivienda, fechas_mes_pasado)

        primer_dia_mes_pasado = (inicio_mes - timedelta(days=1)).replace(day=1)
        consumo_mes_pasado = sum(obtener_consumo_dia(id_vivienda, primer_dia_mes_pasado + timedelta(days=i)) for i in range(dias_transcurridos))

        porcentaje_mes = round(((consumo_mes_actual - consumo_mes_pasado) / consumo_mes_pasado) * 100, 1) if consumo_mes_pasado else None

        # Racha: días consecutivos 
        racha = 0
        for consumo_dia in dias_previos:
            if promedio_habitual and consumo_dia > promedio_habitual * 1.3:
                break
            racha += 1

        
        ya_existe = supabase_get(
            "retroalimentacion_consumo",
            f"id_vivienda=eq.{id_vivienda}&tipo_mensaje=eq.{tipo_mensaje}"
            f"&fecha_registro=gte.{hoy.isoformat()}T00:00:00&select=id_retroalimentacion"
        )
        if not ya_existe:
            supabase_post("retroalimentacion_consumo", {
                "id_vivienda": id_vivienda,
                "tipo_mensaje": tipo_mensaje,
                "mensaje_generado": mensaje,
                "diferencia_consumo": (consumo_hoy - promedio_habitual) if promedio_habitual else None,
            })

        return Response({
            "consumo_hoy_litros": round(consumo_hoy, 2),
            "promedio_habitual_litros": promedio_habitual,
            "estado": estado,
            "color": color,
            "mensaje": mensaje,
            "comparacion_mes": {
                "porcentaje": porcentaje_mes,
                "texto": (f"Este mes: {'+' if porcentaje_mes >= 0 else ''}{porcentaje_mes}% vs. mes anterior"
                          if porcentaje_mes is not None else "Sin datos suficientes todavía."),
            },
            "racha_dias": racha,
            "racha_texto": f"{racha} día(s) seguidos con buen consumo" if racha > 0 else "Empieza tu racha hoy",
        }, status=status.HTTP_200_OK)


TIPS_BASE = [
    {"id": "cerrar_llave", "titulo": "Cerrar la llave mientras te lavas los dientes",
     "impacto": "Ahorra hasta 10L diarios", "icono_drawable": "tip_cerrar_llave"},
    {"id": "reducir_ducha", "titulo": "Reducir el tiempo de ducha a 5 minutos",
     "impacto": "Ahorra hasta 50L diarios", "icono_drawable": "tip_reducir_ducha"},
    {"id": "grifo_platos", "titulo": "Evitar dejar el grifo abierto al lavar platos",
     "impacto": "Reduce el desperdicio innecesario", "icono_drawable": "tip_grifo_platos"},
    {"id": "lavado_vehiculos", "titulo": "Evitar lavar vehículos con manguera",
     "impacto": "Usa balde para ahorrar más agua", "icono_drawable": "tip_lavado_vehiculos"},
]


class RecomendacionesView(APIView):
    """GET /auth/recomendaciones/ — Escenario 1 de PB044"""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsUsuarioAutenticado]

    def get(self, request):
        vivienda = _resolver_vivienda_activa(request.user.id_usuario)
        if not vivienda:
            return Response({"error": "No tienes una vivienda vinculada."}, status=status.HTTP_404_NOT_FOUND)

        nombre = request.user.correo.split("@")[0]
        return Response({
            "saludo": f"¡Hola {nombre}! Basado en tu consumo reciente, tenemos estas sugerencias para ti.",
            "tips": TIPS_BASE,
        }, status=status.HTTP_200_OK)