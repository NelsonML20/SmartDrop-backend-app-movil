from rest_framework import serializers
from .models import Usuario, Rol


class RegistroSerializer(serializers.Serializer):
    nombre    = serializers.CharField(max_length=255)
    apellido  = serializers.CharField(max_length=255)
    correo    = serializers.EmailField(max_length=255)
    contrasena = serializers.CharField(max_length=250, write_only=True)

    def validate_correo(self, value):
        
        if Usuario.objects.filter(correo=value).exists():
            raise serializers.ValidationError("El correo ya está registrado.")
        return value

    def create(self, validated_data):
        import bcrypt

        
        contrasena_bytes = validated_data['contrasena'].encode('utf-8')
        salt = bcrypt.gensalt()
        contrasena_hasheada = bcrypt.hashpw(contrasena_bytes, salt).decode('utf-8')

       
        rol = Rol.objects.get(id_rol=1)

        
        usuario = Usuario.objects.create(
            nombre=validated_data['nombre'],
            apellido=validated_data['apellido'],
            correo=validated_data['correo'],
            contrasena=contrasena_hasheada,
            id_rol=rol
        )
        return usuario
    
class LoginSerializer(serializers.Serializer):
    correo     = serializers.EmailField()
    contrasena = serializers.CharField(write_only=True)

    def validate(self, data):
        import bcrypt
        from rest_framework_simplejwt.tokens import RefreshToken

        correo     = data.get('correo')
        contrasena = data.get('contrasena')

        
        try:
            usuario = Usuario.objects.get(correo=correo)
        except Usuario.DoesNotExist:
            raise serializers.ValidationError("Usuario no encontrado.")

        
        contrasena_bytes = contrasena.encode('utf-8')
        contrasena_bd    = usuario.contrasena.encode('utf-8')

        if not bcrypt.checkpw(contrasena_bytes, contrasena_bd):
            raise serializers.ValidationError("Credenciales incorrectas.")

        
        refresh = RefreshToken()
        refresh['id_usuario'] = usuario.id_usuario
        refresh['correo']     = usuario.correo
        refresh['id_rol']     = usuario.id_rol.id_rol

        data['access']     = str(refresh.access_token)
        data['refresh']    = str(refresh)
        data['id_rol']     = usuario.id_rol.id_rol
        data['id_usuario'] = usuario.id_usuario
        data['nombre']     = usuario.nombre

        return data