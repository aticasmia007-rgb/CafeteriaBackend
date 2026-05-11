from rest_framework import serializers

from .models import DeliverySlot


class SlotTemplateSerializer(serializers.ModelSerializer):
    slot_id = serializers.UUIDField(source='id', read_only=True)
    label = serializers.SerializerMethodField()

    class Meta:
        model = DeliverySlot
        fields = ['slot_id', 'label', 'start_time', 'end_time', 'capacity', 'active']

    def get_label(self, obj):
        return str(obj)


class SlotAvailableSerializer(serializers.ModelSerializer):
    slot_id = serializers.UUIDField(source='id', read_only=True)
    label = serializers.SerializerMethodField()
    remaining = serializers.IntegerField(read_only=True)

    class Meta:
        model = DeliverySlot
        fields = ['slot_id', 'label', 'capacity', 'remaining']

    def get_label(self, obj):
        return str(obj)


class SlotCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverySlot
        fields = ['start_time', 'end_time', 'capacity']


class SlotUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliverySlot
        fields = ['capacity', 'active']
