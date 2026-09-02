# usuarios/consumo_utils.py
"""
Motor de cálculo de consumo. Integra caudal (L/min) → litros.
Optimizado para evitar el patrón N+1: siempre trae el rango completo
de lecturas en UNA sola petición y agrupa/calcula en memoria.
"""

from datetime import datetime, timedelta
from smartdrop.supabase_client import supabase_get, supabase_post
from .sensor_utils import resolver_sensor


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def _integrar_lecturas(lecturas):
    if not lecturas or len(lecturas) < 2:
        return 0.0
    total_litros = 0.0
    for i in range(len(lecturas) - 1):
        v1, v2 = lecturas[i]["valor"], lecturas[i + 1]["valor"]
        t1 = datetime.strptime(lecturas[i]["fecha_registro"][:19], "%Y-%m-%dT%H:%M:%S")
        t2 = datetime.strptime(lecturas[i + 1]["fecha_registro"][:19], "%Y-%m-%dT%H:%M:%S")
        minutos = (t2 - t1).total_seconds() / 60.0
        if minutos > 0:
            total_litros += ((v1 + v2) / 2.0) * minutos
    return round(total_litros, 2)


def _agrupar_lecturas_por_dia(lecturas):
    """Agrupa en memoria (sin más consultas) lecturas ya traídas."""
    grupos = {}
    for l in lecturas:
        dia = l["fecha_registro"][:10]  # 'YYYY-MM-DD'
        grupos.setdefault(dia, []).append(l)
    return grupos


def calcular_consumo_rango(id_vivienda, desde, hasta, sensor=None):
    sensor = sensor or resolver_sensor("flujo")
    if not sensor:
        return 0.0
    lecturas = supabase_get(
        "lectura",
        f"id_sensor=eq.{sensor['id_sensor']}&id_vivienda=eq.{id_vivienda}"
        f"&fecha_registro=gte.{_iso(desde)}&fecha_registro=lte.{_iso(hasta)}"
        f"&order=fecha_registro.asc&select=valor,fecha_registro"
    )
    return _integrar_lecturas(lecturas)


def serie_por_dia(id_vivienda, dias):
    """
    Antes: hasta `dias` × 3 peticiones (una por cada día).
    Ahora: máximo 2-3 peticiones totales, sin importar cuántos días sean.
    """
    sensor = resolver_sensor("flujo")
    if not sensor:
        return []

    hoy = datetime.utcnow().date()
    inicio_rango = hoy - timedelta(days=dias - 1)

    # 1 sola petición: trae TODO el caché existente del rango de una vez
    cache_rows = supabase_get(
        "consumo",
        f"id_vivienda=eq.{id_vivienda}&periodo=eq.dia"
        f"&fecha=gte.{inicio_rango.isoformat()}T00:00:00&fecha=lte.{hoy.isoformat()}T23:59:59"
        f"&select=fecha,consumo_total"
    )
    cache_por_dia = {row["fecha"][:10]: row["consumo_total"] for row in cache_rows}

    # Determina qué días CERRADOS faltan en caché (hoy nunca se cachea)
    dias_faltantes = [
        inicio_rango + timedelta(days=i) for i in range(dias)
        if (inicio_rango + timedelta(days=i)) < hoy
        and (inicio_rango + timedelta(days=i)).isoformat() not in cache_por_dia
    ]

    lecturas_por_dia = {}
    if dias_faltantes:
        # 1 sola petición: trae TODAS las lecturas necesarias de una vez
        desde_dt = datetime.combine(min(dias_faltantes), datetime.min.time())
        hasta_dt = datetime.combine(max(dias_faltantes), datetime.max.time())
        lecturas = supabase_get(
            "lectura",
            f"id_sensor=eq.{sensor['id_sensor']}&id_vivienda=eq.{id_vivienda}"
            f"&fecha_registro=gte.{_iso(desde_dt)}&fecha_registro=lte.{_iso(hasta_dt)}"
            f"&order=fecha_registro.asc&select=valor,fecha_registro"
        )
        lecturas_por_dia = _agrupar_lecturas_por_dia(lecturas)

        # Calcula y cachea en memoria (esto SÍ hace 1 POST por día faltante,
        # pero solo ocurre la primera vez que se pide ese día; luego siempre lee caché)
        for dia in dias_faltantes:
            valor = _integrar_lecturas(lecturas_por_dia.get(dia.isoformat(), []))
            cache_por_dia[dia.isoformat()] = valor
            supabase_post("consumo", {
                "id_vivienda": id_vivienda,
                "fecha": _iso(datetime.combine(dia, datetime.min.time())),
                "consumo_total": valor,
                "consumo_promedio": valor,
                "consumo_maximo": valor,
                "consumo_minimo": valor,
                "periodo": "dia",
                "estado_pago": "pendiente",
            })

    # Día de hoy: siempre en vivo (1 petición más, solo si "hoy" está en el rango)
    if hoy >= inicio_rango:
        cache_por_dia[hoy.isoformat()] = calcular_consumo_rango(
            id_vivienda, datetime.combine(hoy, datetime.min.time()), datetime.utcnow(), sensor=sensor
        )

    return [
        {"fecha": (inicio_rango + timedelta(days=i)).isoformat(),
         "litros": cache_por_dia.get((inicio_rango + timedelta(days=i)).isoformat(), 0.0)}
        for i in range(dias)
    ]


def serie_por_hora_hoy(id_vivienda):
    """1 sola petición: trae todas las lecturas de hoy y agrupa por hora en memoria."""
    sensor = resolver_sensor("flujo")
    if not sensor:
        return []

    ahora = datetime.utcnow()
    inicio_dia = datetime.combine(ahora.date(), datetime.min.time())

    lecturas = supabase_get(
        "lectura",
        f"id_sensor=eq.{sensor['id_sensor']}&id_vivienda=eq.{id_vivienda}"
        f"&fecha_registro=gte.{_iso(inicio_dia)}&fecha_registro=lte.{_iso(ahora)}"
        f"&order=fecha_registro.asc&select=valor,fecha_registro"
    )

    baldes = {h: [] for h in range(ahora.hour + 1)}
    for l in lecturas:
        hora = datetime.strptime(l["fecha_registro"][:19], "%Y-%m-%dT%H:%M:%S").hour
        baldes.setdefault(hora, []).append(l)

    return [{"fecha": f"{h:02d}:00", "litros": _integrar_lecturas(baldes[h])} for h in sorted(baldes.keys())]


def obtener_consumo_dia(id_vivienda, fecha_dia):
    """Se mantiene para uso puntual (1 día específico) — RetroalimentacionView la usa así."""
    hoy = datetime.utcnow().date()
    inicio = datetime.combine(fecha_dia, datetime.min.time())
    fin = datetime.combine(fecha_dia, datetime.max.time())
    sensor = resolver_sensor("flujo")

    if fecha_dia < hoy:
        existente = supabase_get(
            "consumo",
            f"id_vivienda=eq.{id_vivienda}&periodo=eq.dia"
            f"&fecha=eq.{fecha_dia.isoformat()}T00:00:00&select=consumo_total"
        )
        if existente:
            return existente[0]["consumo_total"] or 0.0

        total = calcular_consumo_rango(id_vivienda, inicio, fin, sensor=sensor)
        supabase_post("consumo", {
            "id_vivienda": id_vivienda, "fecha": _iso(inicio), "consumo_total": total,
            "consumo_promedio": total, "consumo_maximo": total, "consumo_minimo": total,
            "periodo": "dia", "estado_pago": "pendiente",
        })
        return total

    return calcular_consumo_rango(id_vivienda, inicio, datetime.utcnow(), sensor=sensor)