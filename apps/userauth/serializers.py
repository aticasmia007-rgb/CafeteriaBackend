from django.contrib.auth import authenticate
from rest_framework import serializers
from .models import CafeteriaUser


class GoogleLoginSerializer(serializers.Serializer):
    token = serializers.CharField()


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data['email'], password=data['password'])
        if not user:
            raise serializers.ValidationError('Email o contraseña incorrectos.')
        if not user.is_active:
            raise serializers.ValidationError('Esta cuenta está desactivada.')
        data['user'] = user
        return data


class RegisterSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, min_length=8)
    name = serializers.CharField(max_length=150)

    def validate_email(self, value):
        if CafeteriaUser.objects.filter(email=value).exists():
            raise serializers.ValidationError('Ya existe una cuenta con este email.')
        return value

    def create(self, validated_data):
        return CafeteriaUser.objects.create_user(
            email=validated_data['email'],
            name=validated_data['name'],
            password=validated_data['password'],
            auth_provider=CafeteriaUser.AuthProvider.INHOUSE,
        )


class UserSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='id', read_only=True)

    class Meta:
        model = CafeteriaUser
        fields = [
            'user_id', 'name', 'email', 'avatar', 'auth_provider',
            'email_verified', 'is_active', 'role', 'created_at',
        ]
        read_only_fields = fields


class EmailVerificationSerializer(serializers.Serializer):
    otp = serializers.CharField(max_length=6, min_length=6)


class PasswordRecoveryConfirmSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField(max_length=6, min_length=6)
    new_password = serializers.CharField(min_length=8)
