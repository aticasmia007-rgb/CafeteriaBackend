from rest_framework import viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated

from config.permissions import IsAdmin, IsStaffOrAdmin
from config.responses import success

from .models import Product
from .serializers import ProductReadSerializer, ProductWriteSerializer


class ProductViewSet(viewsets.ModelViewSet):
    queryset = Product.objects.all()

    def get_serializer_class(self):
        if self.request.method in ('POST', 'PATCH', 'PUT'):
            return ProductWriteSerializer
        return ProductReadSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [AllowAny()]
        elif self.action == 'create':
            return [IsAuthenticated(), IsAdmin()]
        elif self.action in ('update', 'partial_update', 'destroy'):
            return [IsAuthenticated(), IsStaffOrAdmin()]
        return [IsAuthenticated()]

    def get_queryset(self):
        qs = Product.objects.all()
        user = self.request.user
        is_privileged = user.is_authenticated and user.role in ('staff', 'admin')
        if self.action in ('list', 'retrieve') and not is_privileged:
            qs = qs.filter(available=True)
        category = self.request.query_params.get('category')
        if category:
            qs = qs.filter(category__pk=category)
        allergen = self.request.query_params.get('allergen')
        if allergen:
            qs = qs.filter(allergens__pk=allergen)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        stock = serializer.validated_data.get('stock')
        if stock is not None and stock == 0:
            serializer.save(available=False)
        else:
            serializer.save()

    def perform_update(self, serializer):
        stock = serializer.validated_data.get('stock')
        if stock is not None and stock == 0:
            serializer.save(available=False)
        else:
            serializer.save()

    def perform_destroy(self, instance):
        instance.available = False
        instance.save()

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return success(data=serializer.data)
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
            data={'id': str(serializer.instance.id)},
            msg='Producto creado correctamente',
            created=True,
        )

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return success(
            data={'id': str(instance.id)},
            msg='Producto actualizado correctamente',
        )

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return success(msg='Producto eliminado correctamente')
