import datetime
import uuid

from django.conf import settings
from django.db import models


class Order(models.Model):
    class State(models.TextChoices):
        PENDING = 'pending', 'Pending'
        PAID = 'paid', 'Paid'
        PREPARING = 'preparing', 'Preparing'
        READY = 'ready', 'Ready'
        COLLECTED = 'collected', 'Collected'
        CANCELLED = 'cancelled', 'Cancelled'

    VALID_TRANSITIONS = {
        State.PAID: {State.PREPARING, State.COLLECTED},
        State.PREPARING: {State.READY, State.COLLECTED},
        State.READY: {State.COLLECTED},
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='orders',
    )
    slot = models.ForeignKey(
        'deliveryslots.DeliverySlot',
        on_delete=models.PROTECT,
        related_name='orders',
    )
    state = models.CharField(max_length=20, choices=State.choices, default=State.PENDING)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    pickup_code = models.CharField(max_length=10, blank=True, default='')
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"Order {self.id} [{self.state}]"

    def can_transition_to(self, new_state):
        return new_state in self.VALID_TRANSITIONS.get(self.state, set())


class OrderItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(
        'products.Product',
        on_delete=models.PROTECT,
        related_name='order_items',
    )
    quantity = models.PositiveIntegerField()
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    class Meta:
        unique_together = [['order', 'product']]

    def __str__(self):
        return f"{self.quantity}x {self.product.name}"
