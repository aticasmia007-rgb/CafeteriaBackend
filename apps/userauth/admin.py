from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import CafeteriaUser


@admin.register(CafeteriaUser)
class CafeteriaUserAdmin(BaseUserAdmin):
    list_display = ['email', 'name', 'role', 'is_active', 'email_verified', 'auth_provider']
    list_filter = ['role', 'is_active', 'email_verified', 'auth_provider']
    ordering = ['email']
    search_fields = ['email', 'name']
    filter_horizontal = ('groups', 'user_permissions')

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal', {'fields': ('name', 'avatar', 'auth_provider')}),
        ('Status', {'fields': ('is_active', 'email_verified', 'role')}),
        ('Permissions', {'fields': ('is_superuser', 'groups', 'user_permissions')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'name', 'password1', 'password2', 'role'),
        }),
    )
