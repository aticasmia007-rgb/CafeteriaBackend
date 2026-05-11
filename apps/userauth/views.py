from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import CafeteriaUser
from .serializers import (
    EmailVerificationSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    PasswordRecoveryConfirmSerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import send_otp_email, validate_google_token, verify_otp


def _build_auth_response(user):
    refresh = RefreshToken.for_user(user)
    return {
        'status': '00',
        'access_token': str(refresh.access_token),
        'refresh_token': str(refresh),
        'user': UserSerializer(user).data,
    }


class GoogleLoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            payload = validate_google_token(serializer.validated_data['token'])
        except ValueError as exc:
            return Response(
                {'status': '03', 'msg': str(exc), 'errors': []},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        email = payload.get('email')
        user, created = CafeteriaUser.objects.get_or_create(
            email=email,
            defaults={
                'name': payload.get('name', ''),
                'avatar': payload.get('picture', ''),
                'auth_provider': CafeteriaUser.AuthProvider.GOOGLE,
                'email_verified': payload.get('email_verified', False),
            },
        )

        if not created and user.auth_provider == CafeteriaUser.AuthProvider.INHOUSE:
            return Response(
                {'status': '03', 'msg': 'Este email ya está registrado con contraseña.', 'errors': []},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not user.is_active:
            return Response(
                {'status': '04', 'msg': 'Esta cuenta está desactivada.', 'errors': []},
                status=status.HTTP_403_FORBIDDEN,
            )

        return Response(_build_auth_response(user))


class LoginView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(
                {'status': '03', 'msg': 'Email o contraseña no encontrados.', 'errors': []},
                status=status.HTTP_401_UNAUTHORIZED,
            )
        return Response(_build_auth_response(serializer.validated_data['user']))


class RegisterView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        send_otp_email(user)
        return Response(_build_auth_response(user), status=status.HTTP_201_CREATED)


class LogoutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        try:
            RefreshToken(request.data.get('refresh_token')).blacklist()
        except (TokenError, Exception):
            pass
        return Response({'status': '00', 'msg': 'Sesión cerrada correctamente.'})


class SendOTPView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        send_otp_email(request.user)
        return Response({'status': '00', 'msg': 'Código OTP enviado a tu correo.'})


class VerifyEmailView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = EmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not verify_otp(request.user, serializer.validated_data['otp']):
            return Response(
                {'status': '06', 'msg': 'El código OTP no es válido o ha caducado.', 'errors': []},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        return Response({'status': '00', 'msg': 'Email verificado correctamente.'})


class PasswordRecoveryView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get('email')
        try:
            user = CafeteriaUser.objects.get(
                email=email,
                auth_provider=CafeteriaUser.AuthProvider.INHOUSE,
            )
            send_otp_email(user)
        except CafeteriaUser.DoesNotExist:
            pass  # no account enumeration
        return Response({
            'status': '00',
            'msg': 'Si el email está registrado, recibirás un código de recuperación.',
        })


class PasswordRecoveryConfirmView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = PasswordRecoveryConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        try:
            user = CafeteriaUser.objects.get(
                email=data['email'],
                auth_provider=CafeteriaUser.AuthProvider.INHOUSE,
            )
        except CafeteriaUser.DoesNotExist:
            return Response(
                {'status': '06', 'msg': 'El código de recuperación no es válido o ha caducado.', 'errors': []},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        if not verify_otp(user, data['otp'], mark_email_verified=False):
            return Response(
                {'status': '06', 'msg': 'El código de recuperación no es válido o ha caducado.', 'errors': []},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

        user.set_password(data['new_password'])
        user.save(update_fields=['password'])
        return Response({'status': '00', 'msg': 'Contraseña restablecida correctamente.'})
