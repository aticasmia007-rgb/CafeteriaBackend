from django.urls import path
from .views import OrderListCreateView, OrderDetailUpdateView, AllOrdersView

urlpatterns = [
    path('', OrderListCreateView.as_view()),
    path('all/', AllOrdersView.as_view()),
    path('<uuid:pk>/', OrderDetailUpdateView.as_view()),
]
