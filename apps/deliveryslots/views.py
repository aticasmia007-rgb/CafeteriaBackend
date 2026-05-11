import datetime

from django.db.models import Count, F, Q
from django.utils import timezone
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from config.permissions import IsStaffOrAdmin
from config.responses import success, error
from .models import DeliverySlot
from .serializers import (
    SlotAvailableSerializer,
    SlotCreateSerializer,
    SlotTemplateSerializer,
    SlotUpdateSerializer,
)

ACTIVE_ORDER_STATES = ['paid', 'preparing', 'ready', 'collected']


class DeliverySlotViewSet(ModelViewSet):
    http_method_names = ['get', 'post', 'patch', 'delete', 'head', 'options']

    def get_queryset(self):
        return DeliverySlot.objects.all().order_by('start_time')

    def get_permissions(self):
        if self.action == 'available':
            return [AllowAny()]
        if self.action in ('list', 'partial_update', 'slot_orders'):
            return [IsStaffOrAdmin()]
        return [IsStaffOrAdmin()]  # create, destroy → admin enforced in get_permissions below

    def get_serializer_class(self):
        if self.action == 'available':
            return SlotAvailableSerializer
        if self.action == 'create':
            return SlotCreateSerializer
        if self.action == 'partial_update':
            return SlotUpdateSerializer
        return SlotTemplateSerializer

    # --- Public: available slots for a date ---

    @action(detail=False, url_path='available', permission_classes=[AllowAny])
    def available(self, request):
        date_str = request.query_params.get('date')
        if date_str:
            try:
                date = datetime.date.fromisoformat(date_str)
            except ValueError:
                return error(422, '06', 'Formato de fecha inválido. Use YYYY-MM-DD.')
        else:
            date = timezone.localdate()

        qs = DeliverySlot.objects.filter(active=True).annotate(
            remaining=F('capacity') - Count(
                'orders',
                filter=Q(
                    orders__created_at__date=date,
                    orders__state__in=ACTIVE_ORDER_STATES,
                )
            )
        ).filter(remaining__gt=0).order_by('start_time')

        data = SlotAvailableSerializer(qs, many=True).data
        for item in data:
            item['date'] = str(date)
            item['available'] = True
        return success(data=list(data))

    # --- Staff: full template ---

    def list(self, request, *args, **kwargs):
        qs = self.get_queryset()
        return success(data=SlotTemplateSerializer(qs, many=True).data)

    # --- Admin: create ---

    def create(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return error(403, '04', 'Solo el administrador puede crear slots.')
        serializer = SlotCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error(422, '06', 'Los datos de entrada no son válidos.', serializer.errors)
        slot = serializer.save()
        return success(msg='Slot creado correctamente', data={'slot_id': str(slot.id)}, created=True)

    # --- Staff/Admin: update capacity or active ---

    def partial_update(self, request, *args, **kwargs):
        slot = self.get_object()
        serializer = SlotUpdateSerializer(slot, data=request.data, partial=True)
        if not serializer.is_valid():
            return error(422, '06', 'Los datos de entrada no son válidos.', serializer.errors)
        serializer.save()
        return success(msg='Slot actualizado correctamente')

    # --- Admin: delete ---

    def destroy(self, request, *args, **kwargs):
        if request.user.role != 'admin':
            return error(403, '04', 'Solo el administrador puede eliminar slots.')
        slot = self.get_object()
        if slot.orders.exists():
            return error(422, '06', 'No se puede eliminar un slot con pedidos asignados. Desactívalo con PATCH.')
        slot.delete()
        return success(msg='Slot eliminado correctamente')

    # --- Staff/Admin: orders in a slot for a date ---

    @action(detail=True, url_path='orders')
    def slot_orders(self, request, pk=None):
        slot = self.get_object()
        date_str = request.query_params.get('date')
        if not date_str:
            return error(422, '06', 'Se requiere el parámetro ?date=YYYY-MM-DD.')
        try:
            date = datetime.date.fromisoformat(date_str)
        except ValueError:
            return error(422, '06', 'Formato de fecha inválido. Use YYYY-MM-DD.')

        orders = (
            slot.orders
            .filter(created_at__date=date, state__in=ACTIVE_ORDER_STATES)
            .select_related('client')
            .order_by('created_at')
        )

        orders_data = [
            {
                'order_id': str(o.id),
                'pickup_code': o.pickup_code,
                'state': o.state,
                'client': {'name': o.client.name, 'email': o.client.email},
            }
            for o in orders
        ]

        return success(data={
            'slot_id': str(slot.id),
            'label': str(slot),
            'date': str(date),
            'orders_count': len(orders_data),
            'orders': orders_data,
        })
