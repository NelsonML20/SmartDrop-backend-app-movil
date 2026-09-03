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

def _calcular_dias_cerrados_batch(id_vivienda, dias_lista, sensor=None):
    if not dias_lista:
        return {}

    sensor = sensor or resolver_sensor("flujo")
    if not sensor:
        return {d.isoformat(): 0.0 for d in dias_lista}

    minimo, maximo = min(dias_lista), max(dias_lista)

    cache_rows = supabase_get(
        "consumo",
        f"id_vivienda=eq.{id_vivienda}&periodo=eq.dia"
        f"&fecha=gte.{minimo.isoformat()}T00:00:00&fecha=lte.{maximo.isoformat()}T23:59:59"
        f"&select=fecha,consumo_total"
    )
    resultado = {row["fecha"][:10]: (row["consumo_total"] or 0.0) for row in cache_rows}

    faltantes = [d for d in dias_lista if d.isoformat() not in resultado]

    if faltantes:
        desde_dt = datetime.combine(min(faltantes), datetime.min.time())
        hasta_dt = datetime.combine(max(faltantes), datetime.max.time())
        lecturas = supabase_get(
            "lectura",
            f"id_sensor=eq.{sensor['id_sensor']}&id_vivienda=eq.{id_vivienda}"
            f"&fecha_registro=gte.{_iso(desde_dt)}&fecha_registro=lte.{_iso(hasta_dt)}"
            f"&order=fecha_registro.asc&select=valor,fecha_registro"
        )
        lecturas_por_dia = _agrupar_lecturas_por_dia(lecturas)

        filas_nuevas = []
        for dia in faltantes:
            valor = _integrar_lecturas(lecturas_por_dia.get(dia.isoformat(), []))
            resultado[dia.isoformat()] = valor
            filas_nuevas.append({
                "id_vivienda": id_vivienda, "fecha": _iso(datetime.combine(dia, datetime.min.time())),
                "consumo_total": valor, "consumo_promedio": valor, "consumo_maximo": valor,
                "consumo_minimo": valor, "periodo": "dia", "estado_pago": "pendiente",
            })

        if filas_nuevas:
            supabase_post("consumo", filas_nuevas) 

    for d in dias_lista:
        resultado.setdefault(d.isoformat(), 0.0)
    return resultado


def total_consumo_dias(id_vivienda, dias_lista, sensor=None):
    """Suma el consumo de una lista de días específicos (todos cerrados)."""
    return round(sum(_calcular_dias_cerrados_batch(id_vivienda, dias_lista, sensor=sensor).values()), 2)


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
    sensor = resolver_sensor("flujo")
    if not sensor:
        return []

    hoy = datetime.utcnow().date()
    inicio_rango = hoy - timedelta(days=dias - 1)
    dias_cerrados = [inicio_rango + timedelta(days=i) for i in range(dias) if (inicio_rango + timedelta(days=i)) < hoy]

    valores = _calcular_dias_cerrados_batch(id_vivienda, dias_cerrados, sensor=sensor)

    if hoy >= inicio_rango:
        valores[hoy.isoformat()] = calcular_consumo_rango(
            id_vivienda, datetime.combine(hoy, datetime.min.time()), datetime.utcnow(), sensor=sensor
        )

    return [
        {"fecha": (inicio_rango + timedelta(days=i)).isoformat(),
         "litros": valores.get((inicio_rango + timedelta(days=i)).isoformat(), 0.0)}
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