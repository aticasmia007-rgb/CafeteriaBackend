from django.db.models import Count
from rest_framework import viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny, IsAuthenticated

from config.permissions import IsAdmin
from config.responses import success

from .models import Category
from .serializers import CategorySerializer


class CategoryViewSet(viewsets.ModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    pagination_class = None

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        return [IsAuthenticated(), IsAdmin()]

    def get_queryset(self):
        qs = Category.objects.annotate(product_count=Count('products'))
        if self.action in ('list', 'retrieve'):
            user = self.request.user
            if not (user.is_authenticated and user.role in ('staff', 'admin')):
                qs = qs.filter(active=True)
        return qs

    def perform_destroy(self, instance):
        if instance.products.exists():
            count = instance.products.count()
            raise ValidationError({
                'products': f'Hay {count} productos asignados a esta categoría.',
            })
        instance.delete()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        serializer = self.get_serializer(queryset, many=True)
        return success(data=serializer.data)

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return success(data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return success(
            data={'category_id': serializer.instance.category_id},
            msg='Categoría creada correctamente',
            created=True,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success(msg='Categoría actualizada correctamente')

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return success(msg='Categoría eliminada correctamente')
