from rest_framework import serializers

from apps.userauth.models import CafeteriaUser


class ProfileSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='id', read_only=True)
    active = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        model = CafeteriaUser
        fields = [
            'user_id', 'name', 'email', 'avatar', 'auth_provider',
            'email_verified', 'active', 'role', 'created_at',
        ]


class ProfileUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CafeteriaUser
        fields = ['name', 'avatar']


class PasswordChangeSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)


class DeactivateSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, required=False)


class AdminUserSerializer(serializers.ModelSerializer):
    user_id = serializers.UUIDField(source='id', read_only=True)
    active = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        model = CafeteriaUser
        fields = [
            'user_id', 'name', 'email', 'avatar', 'auth_provider',
            'email_verified', 'active', 'role', 'created_at',
        ]


class RoleChangeSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=['client', 'staff', 'admin'])
