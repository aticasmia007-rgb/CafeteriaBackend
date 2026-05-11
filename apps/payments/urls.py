from django.urls import path
from .views import InitiatePaymentView, RedsysWebhookView, PaymentStatusView

urlpatterns = [
    path('', InitiatePaymentView.as_view()),
    path('redsys/notification/', RedsysWebhookView.as_view()),
    path('<uuid:order_id>/', PaymentStatusView.as_view()),
]
