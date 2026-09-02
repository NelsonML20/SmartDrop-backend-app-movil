from rest_framework.permissions import BasePermission


class EsAdministrador(BasePermission):
   
    message = "No tienes permisos de administrador para acceder a este recurso."

    def has_permission(self, request, view):
        usuario = getattr(request, 'user', None)
        return bool(
            usuario
            and getattr(usuario, 'is_authenticated', False)
            and usuario.id_rol == 2
        )


class EsUsuarioAutenticado(BasePermission):

    def has_permission(self, request, view):
        usuario = getattr(request, 'user', None)
        return bool(usuario and getattr(usuario, 'is_authenticated', False))