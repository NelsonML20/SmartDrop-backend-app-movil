from django.contrib import admin
from .models import Rol, Usuario, Sesion

@admin.register(Rol)
class RolAdmin(admin.ModelAdmin):
    list_display = ['id_rol', 'nombre_rol', 'descripcion']

@admin.register(Usuario)
class UsuarioAdmin(admin.ModelAdmin):
    list_display = ['id_usuario', 'nombre', 'apellido', 'correo', 'estado_usuario', 'fecha_registro']

@admin.register(Sesion)
class SesionAdmin(admin.ModelAdmin):
    list_display = ['id_sesion', 'id_usuario', 'fecha_inicio', 'fecha_fin']