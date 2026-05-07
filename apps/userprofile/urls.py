"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.probando),
    # path('me/', views.my_profile), # GET: Obtener perfil / PATCH: Actualizar nombre o avatar
    # path('me/password/', views.change_password), # PATCH: Cambiar contraseña (in-house) 
    # path('me/deactivate/', views.deactivate_account), # PATCH: Desactivar cuenta propia 
    # path('email-otp/', views.send_otp), # GET: Envío de OTP para verificar email 
    # path('email-verification/', views.verify_email), # POST: Verificación de email con OTP 
    # path('admin/users/', views.list_users), # GET: Listar y filtrar usuarios (Admin) 
    # path('admin/users/<str:user_id>/role/', views.change_user_role), # PATCH: Cambiar rol de usuario 
    ]
