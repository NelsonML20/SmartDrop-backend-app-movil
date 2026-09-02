"""
Autenticación de SmartDrop.

Como los usuarios no viven en la tabla auth_user de Django (viven
en Supabase), no podemos usar la autenticación JWT que trae Django REST
Framework por defecto: esa espera encontrar un usuario real en su base
de datos.

En su lugar, se decidio crear el token y armamos un
objeto simple con los datos que ya guardamos dentro del JWT
(id_usuario, correo, id_rol) durante el login.
"""

from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import TokenError


class UsuarioToken:
    

    def __init__(self, payload):
        self.id_usuario   = payload.get('id_usuario')
        self.correo       = payload.get('correo')
        self.id_rol       = payload.get('id_rol')
        self.nombre_rol   = payload.get('nombre_rol')
        self.is_authenticated = True


class SupabaseJWTAuthentication(BaseAuthentication):

    def authenticate(self, request):
        auth_header = request.META.get('HTTP_AUTHORIZATION')

        if not auth_header or not auth_header.startswith('Bearer '):
            return None

        token_str = auth_header.split(' ')[1]

        try:
            token = AccessToken(token_str)
        except TokenError:
            raise AuthenticationFailed('Token inválido o expirado.')

        usuario = UsuarioToken(token.payload)
        return (usuario, token)