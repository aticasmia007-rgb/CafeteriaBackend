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
        from django.conf import settings

        def _get(key):
            val = request.data.get(key, '')
            return val[0] if isinstance(val, list) else val

        merchant_params = _get('Ds_MerchantParameters')
        signature = _get('Ds_Signature')

        print("[REDSYS] Raw body:", request.data)

        # 1. Check required fields
        if not merchant_params or not signature:
            print("[REDSYS] Missing params or signature")
            return Response({}, status=200)

        # 2. Decode and log params (for debugging)
        try:
            import base64, json
            decoded = json.loads(base64.b64decode(merchant_params).decode('utf-8'))
            print("[REDSYS] Decoded params:", decoded)
        except Exception as e:
            print("[REDSYS] Failed to decode params:", e)
            return Response({}, status=200)

        # 3. Validate signature
        redsys = RedsysSignature(settings.REDSYS_SECRET_KEY)
        valid = redsys.validate_notification(merchant_params, signature)
        print("[REDSYS] Signature valid:", valid)

        if not valid:
            print("[REDSYS] Invalid signature, rejecting")
            return Response({}, status=200)

        # 4. Process the payment result
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
