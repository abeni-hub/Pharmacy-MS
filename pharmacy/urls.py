from rest_framework.routers import DefaultRouter
from .views import MedicineViewSet, SaleViewSet, DepartmentViewSet , DashboardViewSet

router = DefaultRouter()
router.register(r'medicines', MedicineViewSet)
router.register(r'sales', SaleViewSet)
router.register(r'departments', DepartmentViewSet)
router.register(r'dashboard', DashboardViewSet, basename='dashboard')

# /api/dashboard/overview/
# /api/dashboard/analytics/

urlpatterns = router.urls
