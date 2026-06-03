# usuarios/views.py

from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import RegistroSerializer, LoginSerializer


class RegistroView(APIView):

    def post(self, request):
        print(f">>> Datos que llegan: {request.data}")
        
        serializer = RegistroSerializer(data=request.data)

        if not serializer.is_valid():
            print(f">>> Errores: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        usuario = serializer.save()
        return Response({
            "mensaje": "Usuario registrado exitosamente.",
            "id_usuario": usuario.id_usuario
        }, status=status.HTTP_201_CREATED)

class LoginView(APIView):

    def post(self, request):
        print(f">>> Login intento: {request.data}")

        serializer = LoginSerializer(data=request.data)

        if not serializer.is_valid():
            print(f">>> Error login: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        
        return Response({
            "mensaje": "Inicio de sesión exitoso.",
            "access":      serializer.validated_data['access'],
            "refresh":     serializer.validated_data['refresh'],
            "id_rol":      serializer.validated_data['id_rol'],
            "id_usuario":  serializer.validated_data['id_usuario'],
            "nombre":      serializer.validated_data['nombre'],
        }, status=status.HTTP_200_OK)