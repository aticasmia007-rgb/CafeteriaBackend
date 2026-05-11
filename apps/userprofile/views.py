from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

from config.permissions import IsAdmin
from config.responses import error, success

from apps.userauth.models import CafeteriaUser

from .serializers import (
    AdminUserSerializer,
    DeactivateSerializer,
    PasswordChangeSerializer,
    ProfileSerializer,
    ProfileUpdateSerializer,
    RoleChangeSerializer,
)


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = ProfileSerializer(request.user)
        return success(data=serializer.data)

    def patch(self, request):
        serializer = ProfileUpdateSerializer(
            request.user, data=request.data, partial=True,
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return success(
            data={
                'user_id': str(request.user.id),
                'name': request.user.name,
                'avatar': request.user.avatar,
            },
            msg='Perfil actualizado correctamente',
        )


class ChangePasswordView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        if user.auth_provider == 'google':
            return error(
                422, '06',
                'Los usuarios registrados con Google no pueden cambiar la contraseña desde aquí.',
            )
        serializer = PasswordChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not user.check_password(serializer.validated_data['current_password']):
            return error(401, '03', 'La contraseña actual no es correcta.')
        user.set_password(serializer.validated_data['new_password'])
        user.save()
        return success(msg='Contraseña actualizada correctamente')


class DeactivateAccountView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        user = request.user
        serializer = DeactivateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if user.auth_provider == 'inhouse':
            password = serializer.validated_data.get('password')
            if not password or not user.check_password(password):
                return error(401, '03', 'La contraseña no es correcta.')
        user.is_active = False
        user.save()
        return success(msg='Cuenta desactivada correctamente')


class AdminUserListView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def get(self, request):
        qs = CafeteriaUser.objects.all()
        search = request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(
                email__icontains=search,
            )
        paginator = PageNumberPagination()
        paginator.page_size = 20
        page = paginator.paginate_queryset(qs, request)
        if page is not None:
            serializer = AdminUserSerializer(page, many=True)
            return success(data=serializer.data)
        serializer = AdminUserSerializer(qs, many=True)
        return success(data=serializer.data)


class AdminUserRoleView(APIView):
    permission_classes = [IsAuthenticated, IsAdmin]

    def patch(self, request, user_id):
        try:
            user = CafeteriaUser.objects.get(id=user_id)
        except CafeteriaUser.DoesNotExist:
            return error(404, '05', 'Usuario no encontrado.')
        serializer = RoleChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user.role = serializer.validated_data['role']
        user.save()
        return success(msg='Rol actualizado correctamente')
