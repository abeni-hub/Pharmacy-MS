from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Medicine, Sale, Department
from .serializers import MedicineSerializer, SaleSerializer, DepartmentSerializer
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.decorators import action
from datetime import timedelta


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]

class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    
class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['department']
    search_fields = ['code_no','brand_name','generic_name']
    ordering_fields = ['expire_date','price','stock']
    # Expired medicines
    @action(detail=False, methods=['get'])
    def expired(self, request):
        today = timezone.now().date()
        expired = Medicine.objects.filter(expire_date__lt=today)
        serializer = self.get_serializer(expired, many=True)
        return Response(serializer.data)

    # Nearly expired (e.g., next 30 days)
    @action(detail=False, methods=['get'])
    def nearly_expired(self, request):
        today = timezone.now().date()
        near_date = today + timedelta(days=30)
        nearly_expired = Medicine.objects.filter(expire_date__gte=today, expire_date__lte=near_date)
        serializer = self.get_serializer(nearly_expired, many=True)
        return Response(serializer.data)

    # Low stock (threshold = 10)
    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        low_stock = Medicine.objects.filter(stock__lte=10, stock__gt=0)
        serializer = self.get_serializer(low_stock, many=True)
        return Response(serializer.data)

    # Stock out
    @action(detail=False, methods=['get'])
    def stock_out(self, request):
        stock_out = Medicine.objects.filter(stock=0)
        serializer = self.get_serializer(stock_out, many=True)
        return Response(serializer.data)

    # Current stock count
    @action(detail=False, methods=['get'])
    def stock(self, request):
        medicines = Medicine.objects.all()
        data = [
            {"code_no": m.code_no, "brand_name": m.brand_name, "stock": m.stock}
            for m in medicines
        ]
        return Response(data)
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all()
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['department']
    search_fields = ['code_no','brand_name','generic_name']
    ordering_fields = ['expire_date','price','stock']

    @action(detail=False, methods=['get'])
    def total_sales(self, request):
        total = sum(s.total_price for s in Sale.objects.all())
        return Response({"total_sales": total})

    # Sales today
    @action(detail=False, methods=['get'])
    def sales_today(self, request):
        today = timezone.now().date()
        sales = Sale.objects.filter(sale_date__date=today)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)

    # Sales by medicine ID
    @action(detail=False, methods=['get'])
    def by_medicine(self, request):
        medicine_id = request.query_params.get('medicine_id')
        if not medicine_id:
            return Response({"error": "medicine_id query param is required"}, status=400)
        sales = Sale.objects.filter(medicine_id=medicine_id)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)

    # Sales by user ID
    @action(detail=False, methods=['get'])
    def by_user(self, request):
        user_id = request.query_params.get('user_id')
        if not user_id:
            return Response({"error": "user_id query param is required"}, status=400)
        sales = Sale.objects.filter(sold_by_id=user_id)
        serializer = self.get_serializer(sales, many=True)
        return Response(serializer.data)
