from django.db import models

class Rol(models.Model):
    id_rol      = models.AutoField(primary_key=True)
    nombre_rol  = models.CharField(max_length=60)
    descripcion = models.CharField(max_length=200, null=True, blank=True)

    class Meta:
        db_table = 'rol'

    def __str__(self):
        return self.nombre_rol


class Usuario(models.Model):
    id_usuario      = models.AutoField(primary_key=True)
    nombre          = models.CharField(max_length=255)
    apellido        = models.CharField(max_length=255)
    correo          = models.EmailField(max_length=255, unique=True)
    contrasena      = models.CharField(max_length=250)
    estado_usuario  = models.BooleanField(default=True)
    fecha_registro  = models.DateTimeField(auto_now_add=True)
    id_rol          = models.ForeignKey(Rol, on_delete=models.PROTECT, db_column='id_rol')

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return f"{self.nombre} {self.apellido}"


class Sesion(models.Model):
    id_sesion    = models.AutoField(primary_key=True)
    token_acceso = models.CharField(max_length=255)
    fecha_inicio = models.DateTimeField(auto_now_add=True)
    fecha_fin    = models.DateTimeField(null=True, blank=True)
    id_usuario   = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column='id_usuario')

    class Meta:
        db_table = 'sesion'