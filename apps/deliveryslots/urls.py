from rest_framework.routers import DefaultRouter
from .views import DeliverySlotViewSet

router = DefaultRouter()
router.register(r'', DeliverySlotViewSet, basename='deliveryslot')

urlpatterns = router.urls
