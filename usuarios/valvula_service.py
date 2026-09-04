import threading
from datetime import datetime, timedelta
from smartdrop.supabase_client import supabase_get, supabase_post, supabase_patch
from .mqtt_client import publicar_comando_valvula, publicar_comando_valvula_simple 


DURACION_MIN = 5
DURACION_MAX = 120

# Registro en memoria de los Timer activos, para poder cancelarlos (Escenario 2)
_timers_activos = {}


def obtener_valvula(id_valvula):
    resultado = supabase_get("valvula", f"id_valvula=eq.{id_valvula}&select=*")
    return resultado[0] if resultado else None

def abrir_remoto(id_valvula, id_usuario, origen_accion):
    valvula = obtener_valvula(id_valvula)
    if not valvula:
        return {"error": "Válvula no encontrada."}, 404

    estado_anterior = valvula["estado_actual"]

    publicar_comando_valvula_simple(valvula["topic_mqtt_comando"], "abrir")

    supabase_patch("valvula", f"id_valvula=eq.{id_valvula}", {
        "estado_actual": "abierta",
        "ultima_apertura": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
    })

    supabase_post("log_valvula", {
        "id_valvula": id_valvula,
        "accion": "abrir",
        "estado_anterior": estado_anterior,
        "estado_nuevo": "abierta",
        "tipo_activacion": "remota",
        "id_usuario": id_usuario,
        "fecha_hora": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "razon": "Apertura remota manual",
        "origen_accion": origen_accion,
    })

    return {"mensaje": "Comando de apertura enviado.", "estado_actual": "abierta"}, 200


def cerrar_remoto(id_valvula, id_usuario, origen_accion):
    valvula = obtener_valvula(id_valvula)
    if not valvula:
        return {"error": "Válvula no encontrada."}, 404

    estado_anterior = valvula["estado_actual"]

    publicar_comando_valvula_simple(valvula["topic_mqtt_comando"], "cerrar")

    supabase_patch("valvula", f"id_valvula=eq.{id_valvula}", {
        "estado_actual": "cerrada",
    })

    supabase_post("log_valvula", {
        "id_valvula": id_valvula,
        "accion": "cerrar",
        "estado_anterior": estado_anterior,
        "estado_nuevo": "cerrada",
        "tipo_activacion": "remota",
        "id_usuario": id_usuario,
        "fecha_hora": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "razon": "Cierre remoto manual",
        "origen_accion": origen_accion,
    })

    return {"mensaje": "Comando de cierre enviado.", "estado_actual": "cerrada"}, 200


def obtener_temporizador_activo(id_valvula):

    ultima_apertura = supabase_get(
        "log_valvula",
        f"id_valvula=eq.{id_valvula}&accion=eq.ABRIR&duracion_programada=not.is.null"
        f"&order=fecha_hora.desc&limit=1&select=*"
    )
    if not ultima_apertura:
        return None

    apertura = ultima_apertura[0]
    inicio = datetime.strptime(apertura["fecha_hora"][:19], "%Y-%m-%dT%H:%M:%S")
    fin_programado = inicio + timedelta(seconds=apertura["duracion_programada"])

    if datetime.utcnow() >= fin_programado:
        return None 

    cierre_posterior = supabase_get(
        "log_valvula",
        f"id_valvula=eq.{id_valvula}&accion=eq.cerrar"
        f"&fecha_hora=gte.{apertura['fecha_hora']}&select=id_log_valvula&limit=1"
    )
    if cierre_posterior:
        return None  

    segundos_restantes = int((fin_programado - datetime.utcnow()).total_seconds())
    return {
        "duracion_programada": apertura["duracion_programada"],
        "segundos_restantes": max(segundos_restantes, 0),
        "inicio": apertura["fecha_hora"],
        "razon": apertura.get("razon"),
    }


def abrir_con_temporizador(id_valvula, duracion_segundos, id_usuario, origen_accion):
    valvula = obtener_valvula(id_valvula)
    if not valvula:
        return {"error": "Válvula no encontrada."}, 404

    # Escenario 2 / punto 5: rechazar si ya hay un temporizador activo
    if obtener_temporizador_activo(id_valvula):
        return {"error": "Ya hay un temporizador activo, cancélalo primero."}, 409

    # Escenario 4: límite de seguridad
    ajustada = False
    if duracion_segundos > DURACION_MAX:
        duracion_segundos = DURACION_MAX
        ajustada = True
    elif duracion_segundos < DURACION_MIN:
        return {"error": f"Duración mínima permitida: {DURACION_MIN} segundos."}, 400

    razon = f"Apertura temporizada de {duracion_segundos} segundos"

    # 1) Registro de INTENCIÓN en log_valvula (con la duración programada)
    supabase_post("log_valvula", {
        "id_valvula": id_valvula,
        "accion": "abrir",
        "estado_anterior": valvula["estado_actual"],
        "estado_nuevo": "abierta",
        "tipo_activacion": "temporizado",
        "id_usuario": id_usuario,
        "fecha_hora": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "duracion_programada": duracion_segundos,
        "razon": razon,
        "origen_accion": origen_accion,
    })

    # 2) Comando real al ESP32 (el ESP32 hará su PROPIO log de confirmación)
    publicar_comando_valvula(valvula["topic_mqtt_comando"], {
        "id_valvula": id_valvula,
        "accion": "abrir",
        "tipo_activacion": "temporizado",
        "id_usuario": id_usuario,
        "origen_accion": origen_accion,
        "razon": razon,
    })

    # 3) Cierre automático programado (limitación: vive en memoria del proceso Django)
    timer = threading.Timer(duracion_segundos, _cerrar_por_temporizador, args=[id_valvula, id_usuario, origen_accion])
    timer.start()
    _timers_activos[id_valvula] = timer

    return {
        "mensaje": f"Válvula abierta por {duracion_segundos} segundos.",
        "duracion_ajustada": ajustada,
        "duracion_segundos": duracion_segundos,
    }, 200


def _cerrar_por_temporizador(id_valvula, id_usuario, origen_accion):
    valvula = obtener_valvula(id_valvula)
    if not valvula or valvula["estado_actual"] != "abierta":
        return  # ya se cerró manualmente, no hacer nada

    publicar_comando_valvula(valvula["topic_mqtt_comando"], {
        "id_valvula": id_valvula,
        "accion": "cerrar",
        "tipo_activacion": "temporizado",
        "id_usuario": id_usuario,
        "origen_accion": origen_accion,
        "razon": "Cierre automático - Tiempo completado",
    })
    _timers_activos.pop(id_valvula, None)


def cancelar_temporizador(id_valvula, id_usuario, origen_accion):
    activo = obtener_temporizador_activo(id_valvula)
    if not activo:
        return {"error": "No hay ningún temporizador activo."}, 404

    timer = _timers_activos.pop(id_valvula, None)
    if timer:
        timer.cancel()

    duracion_real = activo["duracion_programada"] - activo["segundos_restantes"]

    valvula = obtener_valvula(id_valvula)
    supabase_post("log_valvula", {
        "id_valvula": id_valvula,
        "accion": "cerrar",
        "estado_anterior": valvula["estado_actual"] if valvula else "abierta",
        "estado_nuevo": "cerrada",
        "tipo_activacion": "manual",
        "id_usuario": id_usuario,
        "fecha_hora": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
        "duracion_real": duracion_real,
        "razon": "Cierre manual durante temporizador",
        "origen_accion": origen_accion,
    })

    publicar_comando_valvula({
        "id_valvula": id_valvula,
        "accion": "CERRAR",
        "tipo_activacion": "manual",
        "id_usuario": id_usuario,
        "origen_accion": origen_accion,
        "razon": "Cierre manual durante temporizador",
    })

    return {"mensaje": f"Temporizador cancelado. Válvula cerrada después de {duracion_real} seg."}, 200