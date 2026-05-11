from rest_framework import serializers

from .models import Product


class ProductReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['id', 'name', 'description', 'price', 'category', 'allergens', 'image', 'available', 'stock', 'prepare_required']


class ProductWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Product
        fields = ['name', 'description', 'price', 'category', 'allergens', 'image', 'available', 'stock', 'prepare_required']
