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
from django.contrib import admin
from django.urls import path
from . import views

urlpatterns = [
    path('', views.probando),
    # path('google/', views.google_login), # POST: Login con Google SSO 
    # path('login/', views.login_in_house), # POST: Login con email y contraseña 
    # path('register/', views.register_in_house), # POST: Registro de nuevo usuario 
    # path('logout/', views.logout), # POST: Invalida el token de sesión
    # path('password-recovery/', views.password_recovery), # POST: Envía OTP al email 
    # path('password-recovery/confirm/', views.confirm_recovery), # POST: Valida OTP y actualiza contraseña 
]
