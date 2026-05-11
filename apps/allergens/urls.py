from rest_framework.routers import DefaultRouter

from .views import AllergenViewSet

router = DefaultRouter()
router.register(r'', AllergenViewSet, basename='allergens')
urlpatterns = router.urls
