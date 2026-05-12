import random
import string
from decimal import Decimal

from django.utils import timezone

from apps.products.models import Product
from .models import Order, OrderItem


def generate_pickup_code():
    chars = string.ascii_uppercase + string.digits
    while True:
        code = ''.join(random.choices(chars, k=6))
        if not Order.objects.filter(pickup_code=code).exists():
            return code


def _generate_payment_provider_id() -> str:
    existing = (
        Order.objects
        .exclude(payment_provider_id='')
        .values_list('payment_provider_id', flat=True)
    )
    nums = []
    for r in existing:
        try:
            nums.append(int(r))
        except (ValueError, TypeError):
            pass
    max_num = max(nums, default=0)
    return str(max_num + 1).zfill(4)


def create_order(client, slot, items_data):
    total = Decimal('0')
    resolved = []
    for item in items_data:
        product = Product.objects.select_for_update().get(id=item['product_id'])
        unit_price = product.price
        total += unit_price * item['quantity']
        resolved.append((product, item['quantity'], unit_price))

    order = Order.objects.create(
        client=client,
        slot=slot,
        total=total,
        payment_provider_id=_generate_payment_provider_id(),
    )
    for product, quantity, unit_price in resolved:
        OrderItem.objects.create(
            order=order,
            product=product,
            quantity=quantity,
            unit_price=unit_price,
        )
    return order


def confirm_order_payment(order):
    from django.db import transaction
    with transaction.atomic():
        order.state = Order.State.PAID
        order.pickup_code = generate_pickup_code()
        order.paid_at = timezone.now()
        order.save(update_fields=['state', 'pickup_code', 'paid_at'])

        for item in order.items.select_related('product').select_for_update():
            product = item.product
            product.stock = max(0, product.stock - item.quantity)
            if product.stock == 0:
                product.available = False
            product.save(update_fields=['stock', 'available'])


def cancel_order(order):
    order.state = Order.State.CANCELLED
    order.save(update_fields=['state'])
