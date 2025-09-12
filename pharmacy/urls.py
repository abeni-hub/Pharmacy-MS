from rest_framework.routers import DefaultRouter
from .views import MedicineViewSet, SaleViewSet, DepartmentViewSet

router = DefaultRouter()
router.register(r'medicines', MedicineViewSet)
router.register(r'sales', SaleViewSet)
router.register(r'departments', DepartmentViewSet)


urlpatterns = router.urls
