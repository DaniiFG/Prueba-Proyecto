# auth_service/auth_app/views.py
from rest_framework import status, generics
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from django.contrib.auth import authenticate
from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import uuid
import logging

from .models import User, PasswordResetToken
from .serializers import (
    UserSerializer, 
    UserLoginSerializer, 
    UserProfileSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer
)

logger = logging.getLogger(__name__)

class UserRegisterView(generics.CreateAPIView):
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [AllowAny]
    
    def create(self, request, *args, **kwargs):
        logger.debug(f"Datos de registro recibidos: {request.data}")
        serializer = self.get_serializer(data=request.data)
        
        if not serializer.is_valid():
            logger.debug(f"Errores de validación: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        user = serializer.save()
        logger.debug(f"Usuario creado con ID: {user.id}")
        
        # Generar tokens JWT para el nuevo usuario
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserProfileSerializer(user).data
        }, status=status.HTTP_201_CREATED)

class UserLoginView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        logger.debug(f"Intento de login: {request.data}")
        serializer = UserLoginSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.debug(f"Errores de validación: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        password = serializer.validated_data['password']
        
        user = authenticate(request, username=email, password=password)
        
        if user is None:
            logger.debug(f"Autenticación fallida para: {email}")
            return Response({'error': 'Credenciales inválidas'}, status=status.HTTP_401_UNAUTHORIZED)
        
        logger.debug(f"Login exitoso para usuario: {user.id} - {user.email}")
        refresh = RefreshToken.for_user(user)
        
        # Actualizar last_login
        user.last_login = timezone.now()
        user.save(update_fields=['last_login'])
        
        return Response({
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserProfileSerializer(user).data
        })

class UserProfileView(generics.RetrieveUpdateAPIView):
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]
    
    def get_object(self):
        return self.request.user


class PasswordResetRequestView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        logger.debug(f"Solicitud de restablecimiento de contraseña: {request.data}")
        serializer = PasswordResetRequestSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.debug(f"Errores de validación: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        email = serializer.validated_data['email']
        
        try:
            user = User.objects.get(email=email)
            logger.debug(f"Usuario encontrado: {user.id}")
            
            # Crear token para restablecimiento
            token_value = str(uuid.uuid4())
            expires_at = timezone.now() + timedelta(hours=1)
            
            # Guardar token en la base de datos
            reset_token = PasswordResetToken.objects.create(
                user=user,
                token=token_value,
                expires_at=expires_at
            )
            
            # Crear enlace de restablecimiento (aquí usarías la URL de tu frontend)
            reset_link = f"{settings.FRONTEND_URL}/reset-password/{token_value}"
            
            # Enviar correo con el enlace de restablecimiento
            try:
                send_mail(
                    'Restablecimiento de contraseña',
                    f'Hola {user.first_name},\n\nHaz clic en el siguiente enlace para restablecer tu contraseña:\n{reset_link}\n\nEste enlace expirará en 1 hora.',
                    settings.DEFAULT_FROM_EMAIL,
                    [email],
                    fail_silently=False,
                )
                logger.debug(f"Correo de restablecimiento enviado a: {email}")
            except Exception as e:
                logger.error(f"Error al enviar correo: {str(e)}")
                # No fallamos la petición aunque falle el correo
            
            return Response({'message': 'Se ha enviado un correo con instrucciones para restablecer tu contraseña.'}, 
                        status=status.HTTP_200_OK)
                        
        except User.DoesNotExist:
            logger.debug(f"Usuario no encontrado: {email}")
            # Por seguridad, no revelamos que el usuario no existe
            return Response({'message': 'Se ha enviado un correo con instrucciones para restablecer tu contraseña.'}, 
                        status=status.HTTP_200_OK)
        except Exception as e:
            logger.error(f"Error al procesar restablecimiento: {str(e)}")
            return Response({'error': 'Error al procesar la solicitud'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PasswordResetConfirmView(APIView):
    permission_classes = [AllowAny]
    
    def post(self, request, *args, **kwargs):
        logger.debug(f"Confirmación de restablecimiento de contraseña: {request.data}")
        serializer = PasswordResetConfirmSerializer(data=request.data)
        
        if not serializer.is_valid():
            logger.debug(f"Errores de validación: {serializer.errors}")
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        token_value = serializer.validated_data['token']
        password = serializer.validated_data['password']
        
        try:
            # Obtener token y usuario
            reset_token = PasswordResetToken.objects.get(token=token_value)
            
            # Verificar si el token es válido
            if not reset_token.is_valid():
                logger.debug(f"Token inválido o expirado: {token_value}")
                return Response({'error': 'El token ha expirado o ya ha sido utilizado'}, 
                                status=status.HTTP_400_BAD_REQUEST)
            
            user = reset_token.user
            logger.debug(f"Token válido para usuario: {user.id}")
            
            # Cambiar contraseña
            user.set_password(password)
            user.save()
            logger.debug(f"Contraseña actualizada para usuario: {user.id}")
            
            # Marcar token como usado
            reset_token.is_used = True
            reset_token.save()
            
            # Generar nuevos tokens JWT para el usuario
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'message': 'Contraseña restablecida con éxito.',
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserProfileSerializer(user).data
            }, status=status.HTTP_200_OK)
            
        except PasswordResetToken.DoesNotExist:
            logger.debug(f"Token no encontrado: {token_value}")
            return Response({'error': 'Token inválido'}, status=status.HTTP_400_BAD_REQUEST)
        except Exception as e:
            logger.error(f"Error al restablecer contraseña: {str(e)}")
            return Response({'error': 'Error al procesar la solicitud'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

# Create your views here.
