from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .authentication import SupabaseJWTAuthentication
from .permissions import EsAdministrador, EsUsuarioAutenticado
from . import valvula_service


class ValvulaEstadoView(APIView):
    """GET /admin/valvula/<id>/estado/ — usuarios y admin pueden consultar (Escenario 5)"""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsUsuarioAutenticado]

    def get(self, request, id_valvula):
        valvula = valvula_service.obtener_valvula(id_valvula)
        if not valvula:
            return Response({"error": "Válvula no encontrada."}, status=status.HTTP_404_NOT_FOUND)

        timer = valvula_service.obtener_temporizador_activo(id_valvula)
        return Response({
            "estado_actual": valvula["estado_actual"],
            "temporizador_activo": timer,
        }, status=status.HTTP_200_OK)
    

class ValvulaAbrirRemotoView(APIView):
    """POST /api/valvula/<id>/abrir-remoto/ — solo admin"""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsAdministrador]

    def post(self, request, id_valvula):
        origen_accion = "app" if request.data.get("origen") == "app" else "web"
        resultado, codigo = valvula_service.abrir_remoto(id_valvula, request.user.id_usuario, origen_accion)
        return Response(resultado, status=codigo)


class ValvulaCerrarRemotoView(APIView):
    """POST /api/valvula/<id>/cerrar-remoto/ — solo admin"""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsAdministrador]

    def post(self, request, id_valvula):
        origen_accion = "app" if request.data.get("origen") == "app" else "web"
        resultado, codigo = valvula_service.cerrar_remoto(id_valvula, request.user.id_usuario, origen_accion)
        return Response(resultado, status=codigo)


class ValvulaAbrirTemporizadorView(APIView):
    """POST /admin/valvula/<id>/abrir-temporizador/ — solo admin"""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsAdministrador]

    def post(self, request, id_valvula):
        duracion = request.data.get("duracion_segundos")
        if not isinstance(duracion, int):
            return Response({"error": "duracion_segundos debe ser un entero."}, status=status.HTTP_400_BAD_REQUEST)

        origen_accion = "app" if request.data.get("origen") == "app" else "WEB"
        resultado, codigo = valvula_service.abrir_con_temporizador(
            id_valvula, duracion, request.user.id_usuario, origen_accion
        )
        return Response(resultado, status=codigo)


class ValvulaCancelarView(APIView):
    """POST /admin/valvula/<id>/cancelar/ — solo admin"""
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsAdministrador]

    def post(self, request, id_valvula):
        origen_accion = "app" if request.data.get("origen") == "app" else "WEB"
        resultado, codigo = valvula_service.cancelar_temporizador(
            id_valvula, request.user.id_usuario, origen_accion
        )
        return Response(resultado, status=codigo)