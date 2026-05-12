from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from config.responses import success, error
from apps.orders.models import Order
from .services import RedsysSignature, build_payment_params, process_webhook


class InitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')
        if not order_id:
            return error(422, '06', 'Se requiere order_id.')

        try:
            order = Order.objects.get(id=order_id, client=request.user)
        except Order.DoesNotExist:
            return error(404, '05', 'Pedido no encontrado.')

        if order.state != Order.State.PENDING:
            return error(422, '06', f"El pedido no está en estado pendiente (estado actual: {order.state}).")

        params = build_payment_params(order)
        return success(data=params)


class RedsysWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):

        print("[PAYMENT] Received webhook with data:", request.data)
        merchant_params = request.data.get('Ds_MerchantParameters', '')
        signature = request.data.get('Ds_Signature', '')
        secret_key = __import__('django.conf', fromlist=['settings']).settings.REDSYS_SECRET_KEY

        if not merchant_params or not signature:
            return Response({}, status=200)

        redsys = RedsysSignature(secret_key)
        if not redsys.validate_notification(merchant_params, signature):
            return Response({}, status=200)

        process_webhook(merchant_params)
        return Response({}, status=200)


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, order_id):
        try:
            order = Order.objects.get(id=order_id, client=request.user)
        except Order.DoesNotExist:
            return error(404, '05', 'Pedido no encontrado.')

        data = {
            'order_id': str(order.id),
            'payment_state': order.state,
            'paid_at': order.paid_at,
        }
        if order.state == Order.State.PAID:
            data['pickup_code'] = order.pickup_code

        return success(data=data)
