import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import CafeteriaUserManager


class CafeteriaUser(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        CLIENT = 'client', 'Client'
        STAFF = 'staff', 'Staff'
        ADMIN = 'admin', 'Admin'

    class AuthProvider(models.TextChoices):
        GOOGLE = 'google', 'Google'
        INHOUSE = 'inhouse', 'In-house'

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True)
    name = models.CharField(max_length=150)
    avatar = models.URLField(blank=True, default='')
    auth_provider = models.CharField(
        max_length=10, choices=AuthProvider.choices, default=AuthProvider.INHOUSE
    )
    email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.CLIENT)
    created_at = models.DateTimeField(auto_now_add=True)

    otp_code = models.CharField(max_length=6, blank=True)
    otp_created_at = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['name']

    objects = CafeteriaUserManager()

    @property
    def is_staff(self):
        return self.role in (self.Role.STAFF, self.Role.ADMIN)

    def __str__(self):
        return self.email
