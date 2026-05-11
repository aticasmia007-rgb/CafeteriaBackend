from decimal import Decimal

from rest_framework import serializers

from apps.products.models import Product
from .models import Order, OrderItem


class OrderItemCreateSerializer(serializers.Serializer):
    product_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)

    def validate_product_id(self, value):
        try:
            product = Product.objects.get(id=value)
        except Product.DoesNotExist:
            raise serializers.ValidationError("Producto no encontrado.")
        if not product.available:
            raise serializers.ValidationError(f"El producto '{product.name}' no está disponible.")
        if product.stock < 1:
            raise serializers.ValidationError(f"El producto '{product.name}' está agotado.")
        return value

    def validate(self, data):
        product = Product.objects.get(id=data['product_id'])
        if product.stock < data['quantity']:
            raise serializers.ValidationError(
                f"Stock insuficiente para '{product.name}'. Disponible: {product.stock}."
            )
        return data


class OrderCreateSerializer(serializers.Serializer):
    slot_id = serializers.UUIDField()
    items = OrderItemCreateSerializer(many=True)

    def validate_slot_id(self, value):
        import datetime
        from django.db.models import Count, F, Q
        from apps.deliveryslots.models import DeliverySlot

        try:
            slot = DeliverySlot.objects.get(id=value, active=True)
        except DeliverySlot.DoesNotExist:
            raise serializers.ValidationError("Franja horaria no válida o inactiva.")

        today = datetime.date.today()
        occupied = Order.objects.filter(
            slot=slot,
            created_at__date=today,
            state__in=['paid', 'preparing', 'ready', 'collected'],
        ).count()
        if occupied >= slot.capacity:
            raise serializers.ValidationError("El slot seleccionado está completo para hoy.")
        return value

    def validate_items(self, items):
        if not items:
            raise serializers.ValidationError("El pedido debe contener al menos un producto.")
        product_ids = [item['product_id'] for item in items]
        if len(product_ids) != len(set(str(pid) for pid in product_ids)):
            raise serializers.ValidationError("No puede haber productos duplicados en el pedido.")
        return items


class OrderItemReadSerializer(serializers.ModelSerializer):
    product_id = serializers.UUIDField(source='product.id')
    product_name = serializers.CharField(source='product.name')

    class Meta:
        model = OrderItem
        fields = ['id', 'product_id', 'product_name', 'quantity', 'unit_price']


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    slot = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'state', 'total', 'pickup_code', 'slot', 'items', 'paid_at', 'created_at']

    def get_slot(self, obj):
        return {
            'id': str(obj.slot.id),
            'label': str(obj.slot),
        }


class OrderStaffReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    slot = serializers.SerializerMethodField()
    client = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = ['id', 'state', 'total', 'pickup_code', 'slot', 'client', 'items', 'paid_at', 'created_at']

    def get_slot(self, obj):
        return {
            'id': str(obj.slot.id),
            'label': str(obj.slot),
        }

    def get_client(self, obj):
        return {
            'id': str(obj.client.id),
            'name': obj.client.name,
            'email': obj.client.email,
        }


class OrderStateUpdateSerializer(serializers.Serializer):
    state = serializers.ChoiceField(choices=Order.State.choices)

    def validate_state(self, value):
        order = self.context['order']
        if not order.can_transition_to(value):
            raise serializers.ValidationError(
                f"No se puede pasar de '{order.state}' a '{value}'."
            )
        return value
