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
    #path('available/', views.available_slots), # GET: Slots con capacidad para una fecha [cite: 514]
    path('', views.slot_template), # GET: Plantilla semanal completa de slots [cite: 517]
    # path('create/', views.create_slot), # POST: Añadir franja horaria a la plantilla [cite: 519]
    # path('<int:id>/', views.update_slot), # PATCH: Actualizar capacidad o estado [cite: 522]
    # path('<int:id>/delete/', views.delete_slot), # DELETE: Eliminar slot de la plantilla [cite: 525]
    # path('<int:id>/orders/', views.slot_orders), # GET: Pedidos asignados a un slot y fecha [cite: 527]

   ]
