from django.contrib import admin
from .models import DeliverySlot


@admin.register(DeliverySlot)
class DeliverySlotAdmin(admin.ModelAdmin):
    list_display = ['__str__', 'capacity', 'active']
    list_filter = ['active']
