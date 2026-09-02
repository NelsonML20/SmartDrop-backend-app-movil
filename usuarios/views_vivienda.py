"""
Vinculación de vivienda — replica el modelo de negocio real de ANDA/AES:
la vivienda ya existe en el sistema, el usuario
solo la vincula desde la app con su Número de cuenta + nombre del titular.
"""

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .authentication import SupabaseJWTAuthentication
from .permissions import EsUsuarioAutenticado
from smartdrop.supabase_client import supabase_get, supabase_patch


class MisViviendasView(APIView):
    """GET /auth/mis-viviendas/ — todas las viviendas vinculadas al usuario logueado."""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsUsuarioAutenticado]

    def get(self, request):
        id_usuario = request.user.id_usuario
        viviendas = supabase_get(
            "vivienda",
            f"id_usuario_propietario=eq.{id_usuario}&select=*"
        )
        return Response({"viviendas": viviendas}, status=status.HTTP_200_OK)


class VincularViviendaView(APIView):
    """POST /auth/vincular-vivienda/ — reclama una vivienda existente."""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsUsuarioAutenticado]

    def post(self, request):
        numero_cuenta  = request.data.get('numero_cuenta', '').strip()
        nombre_titular = request.data.get('nombre_completo_titular', '').strip()

        if not numero_cuenta or not nombre_titular:
            return Response({"error": "Completa todos los campos."}, status=status.HTTP_400_BAD_REQUEST)

        
        resultado = supabase_get("vivienda", f"nic=eq.{numero_cuenta}&select=*")

        if not resultado:
            return Response(
                {"error": "No encontramos ese número de cuenta. Verifica el dato o contacta a soporte."},
                status=status.HTTP_404_NOT_FOUND
            )

        vivienda = resultado[0]

        # Validar que el nombre coincida con la persona registrada
        nombre_bd = (vivienda.get('nombre_completo_titular') or '').strip().lower()
        if nombre_bd != nombre_titular.lower():
            return Response(
                {"error": "El nombre no coincide con el titular registrado para esa cuenta."},
                status=status.HTTP_400_BAD_REQUEST
            )

        propietario_actual = vivienda.get('id_usuario_propietario')
        id_usuario = request.user.id_usuario

        if propietario_actual == id_usuario:
            return Response(
                {"mensaje": "Ya tienes esta vivienda vinculada.", "vivienda": vivienda},
                status=status.HTTP_200_OK
            )

        if propietario_actual is not None:
            return Response(
                {"error": "Esta vivienda ya está vinculada a otra cuenta."},
                status=status.HTTP_409_CONFLICT
            )

        respuesta = supabase_patch(
            "vivienda",
            f"id_vivienda=eq.{vivienda['id_vivienda']}",
            {"id_usuario_propietario": id_usuario}
        )

        if respuesta.status_code in [200, 204]:
            from .vivienda_utils import invalidar_cache_vivienda
            invalidar_cache_vivienda(id_usuario)
            return Response(
                {"mensaje": "Vivienda vinculada exitosamente.", "vivienda": vivienda},
                status=status.HTTP_200_OK
            )
        else:
            return Response({"error": "No se pudo vincular la vivienda."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)