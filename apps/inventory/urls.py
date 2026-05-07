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
    path('', views.full_inventory), # GET: Listado completo de stock y disponibilidad 
    # path('<str:product_id>/', views.inventory_detail), # GET: Estado de stock de un producto
    # path('<str:product_id>/update/', views.update_stock), # PATCH: Actualizar stock o umbral de alerta 
    # path('alerts/', views.stock_alerts), # GET: Productos por debajo del umbral de stock 
    ]
