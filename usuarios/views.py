from rest_framework.views import APIView
from rest_framework.response import Response
from .authentication import SupabaseJWTAuthentication
from .permissions import EsAdministrador
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken
from smartdrop.supabase_client import supabase_get, supabase_post
import bcrypt
from django.contrib.auth.hashers import check_password
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status



class RegistroView(APIView):

    def post(self, request):
        datos      = request.data
        nombre     = datos.get('nombre', '').strip()
        apellido   = datos.get('apellido', '').strip()
        correo     = datos.get('correo', '').strip()
        contrasena = datos.get('contrasena', '').strip()

        if not nombre or not apellido or not correo or not contrasena:
            return Response({"error": "Completa todos los campos."}, status=status.HTTP_400_BAD_REQUEST)

        resultado = supabase_get("usuario", f"correo=eq.{correo}&select=id_usuario")
        if resultado:
            return Response({"error": "El correo ya está registrado."}, status=status.HTTP_400_BAD_REQUEST)

        contrasena_bytes    = contrasena.encode('utf-8')
        salt                = bcrypt.gensalt()
        contrasena_hasheada = bcrypt.hashpw(contrasena_bytes, salt).decode('utf-8')

        nuevo_usuario = {
            "nombre":     nombre,
            "apellido":   apellido,
            "correo":     correo,
            "contrasena": contrasena_hasheada,
            "id_rol":     1
        }

        respuesta = supabase_post("usuario", nuevo_usuario)

        if respuesta.status_code in [200, 201]:
            usuario = respuesta.json()[0]
            return Response({
                "mensaje":    "Usuario registrado exitosamente.",
                "id_usuario": usuario.get("id_usuario")
            }, status=status.HTTP_201_CREATED)
        else:
            return Response({"error": "Error al registrar usuario."}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LoginView(APIView):

    def post(self, request):
        datos      = request.data
        correo     = datos.get('correo', '').strip()
        contrasena = datos.get('contrasena', '').strip()

        if not correo or not contrasena:
            return Response({"error": "Completa todos los campos."}, status=status.HTTP_400_BAD_REQUEST)

        # Se trae el usuario con su rol
        resultado = supabase_get("usuario", f"correo=eq.{correo}&select=*,rol(nombre_rol)")

        if not resultado:
            return Response({"error": "Correo o contraseña incorrectos."}, status=status.HTTP_400_BAD_REQUEST)

        usuario       = resultado[0]
        contrasena_bd = usuario['contrasena']

        # --- INICIO DE LA LÓGICA DE VALIDACIÓN ADAPTATIVA ---
        contrasena_valida = False

        if contrasena_bd.startswith('pbkdf2_'):
            # Validación para cuentas creadas en la WEB (Django nativo)
            contrasena_valida = check_password(contrasena, contrasena_bd)
        else:
            # Validación para cuentas creadas en la APP (Bcrypt)
            try:
                contrasena_valida = bcrypt.checkpw(
                    contrasena.encode('utf-8'), 
                    contrasena_bd.encode('utf-8')
                )
            except ValueError:
                contrasena_valida = False
        
        if not contrasena_valida:
            return Response({"error": "Correo o contraseña incorrectos."}, status=status.HTTP_400_BAD_REQUEST)
        # --- FIN DE LA LÓGICA DE VALIDACIÓN ADAPTATIVA ---

        # Se extrae el nombre del rol desde el objeto anidado 
        nombre_rol = usuario.get('rol', {}).get('nombre_rol', 'usuario')

        refresh = RefreshToken()
        refresh['id_usuario']  = usuario['id_usuario']
        refresh['correo']      = usuario['correo']
        refresh['id_rol']      = usuario['id_rol']
        refresh['nombre_rol']  = nombre_rol

        return Response({
            "mensaje":    "Inicio de sesión exitoso.",
            "access":     str(refresh.access_token),
            "refresh":    str(refresh),
            "id_rol":     usuario['id_rol'],
            "nombre_rol": nombre_rol,
            "id_usuario": usuario['id_usuario'],
            "nombre":     usuario['nombre'],
        }, status=status.HTTP_200_OK)

class AdminOnlyView(APIView):
  
    authentication_classes = [SupabaseJWTAuthentication]
    permission_classes     = [EsAdministrador]

    def get(self, request):
        return Response({
            "mensaje":    f"Bienvenido administrador {request.user.correo}",
            "id_usuario": request.user.id_usuario,
            "id_rol":     request.user.id_rol,
        })

