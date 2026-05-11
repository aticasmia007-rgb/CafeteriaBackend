from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from apps.allergens.models import Allergen
from apps.categories.models import Category

from .models import Product


class CategoryNestedSerializer(serializers.Serializer):
    category_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class AllergenNestedSerializer(serializers.Serializer):
    allergen_id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    icon = serializers.CharField(read_only=True)


class ProductReadSerializer(serializers.ModelSerializer):
    category = CategoryNestedSerializer(many=True, read_only=True)
    allergens = AllergenNestedSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'description', 'price', 'category', 'allergens',
            'image', 'available', 'stock', 'prepare_required',
        ]


class ProductWriteSerializer(serializers.ModelSerializer):
    category = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Category.objects.all(),
    )
    allergens = serializers.PrimaryKeyRelatedField(
        many=True, queryset=Allergen.objects.all(),
    )

    class Meta:
        model = Product
        fields = [
            'name', 'description', 'price', 'category', 'allergens',
            'image', 'available', 'stock', 'prepare_required',
        ]
