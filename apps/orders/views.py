from django.db import transaction
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import IsAuthenticated

from config.permissions import IsStaffOrAdmin
from config.responses import success, error
from apps.deliveryslots.models import DeliverySlot
from .models import Order
from .serializers import (
    OrderCreateSerializer,
    OrderReadSerializer,
    OrderStaffReadSerializer,
    OrderStateUpdateSerializer,
)
from . import services


class OrderListCreateView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        orders = Order.objects.filter(client=request.user).select_related('slot').prefetch_related('items__product')
        return success(data=OrderReadSerializer(orders, many=True).data)

    def post(self, request):
        serializer = OrderCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(422, '06', 'Los datos de entrada no son válidos.', serializer.errors)

        data = serializer.validated_data
        slot = DeliverySlot.objects.get(id=data['slot_id'])

        with transaction.atomic():
            order = services.create_order(
                client=request.user,
                slot=slot,
                items_data=data['items'],
            )

        return success(data=OrderReadSerializer(order).data, created=True)


class OrderDetailUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_order(self, pk, user):
        try:
            order = Order.objects.select_related('slot', 'client').prefetch_related('items__product').get(pk=pk)
        except Order.DoesNotExist:
            return None, error(404, '05', 'Pedido no encontrado.')

        print('--'*50)
        print(order)
        if user.role not in ('staff', 'admin') and order.client != user:
            return None, error(403, '04', 'No tienes permiso para acceder a este pedido.')

        return order, None

    def get(self, request, pk):
        order, err = self._get_order(pk, request.user)
        if err:
            return err
        serializer = OrderStaffReadSerializer if request.user.role in ('staff', 'admin') else OrderReadSerializer
        return success(data=serializer(order).data)

    def patch(self, request, pk):
        order, err = self._get_order(pk, request.user)
        if err:
            return err

        if request.user.role not in ('staff', 'admin'):
            return error(403, '04', 'Solo el personal puede cambiar el estado del pedido.')

        serializer = OrderStateUpdateSerializer(data=request.data, context={'order': order})
        if not serializer.is_valid():
            return error(422, '06', 'Los datos de entrada no son válidos.', serializer.errors)

        new_state = serializer.validated_data['state']
        order.state = new_state
        order.save(update_fields=['state'])
        return success(data=OrderReadSerializer(order).data)


class AllOrdersView(APIView):
    permission_classes = [IsStaffOrAdmin ]

    def get(self, request):
        qs = Order.objects.select_related('slot', 'client').prefetch_related('items__product')

        state = request.query_params.get('state')
        if state:
            qs = qs.filter(state=state)

        slot_id = request.query_params.get('slot_id')
        if slot_id:
            qs = qs.filter(slot_id=slot_id)

        return success(data=OrderStaffReadSerializer(qs, many=True).data)
