"""
Cliente MQTT de solo publicación. Conexión corta: conecta, publica,
desconecta — no mantiene un listener permanente porque el ESP32 ya
escribe su propio estado directo a Supabase (ver electrovalvula.ino).
"""

import os
import json
import ssl
import paho.mqtt.client as mqtt

MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", 8883))
MQTT_USER = os.getenv("MQTT_USER")
MQTT_PASSWORD = os.getenv("MQTT_PASSWORD")
MQTT_ID_DISPOSITIVO = os.getenv("MQTT_ID_DISPOSITIVO", "esp32_principal")


def publicar_comando_valvula(topic: str, payload: dict):
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
    client.loop_start()
    client.publish(topic, json.dumps(payload), qos=1)
    client.loop_stop()
    client.disconnect()


def publicar_comando_valvula_simple(topic: str, mensaje: str):
    client = mqtt.Client()
    client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    client.tls_set(cert_reqs=ssl.CERT_NONE)
    client.connect(MQTT_HOST, MQTT_PORT, keepalive=10)
    client.loop_start()
    client.publish(topic, mensaje, qos=1)
    client.loop_stop()
    client.disconnect()