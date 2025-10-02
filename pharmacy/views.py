from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Medicine, Sale, Department , Refill , SaleItem
from .serializers import MedicineSerializer, SaleSerializer, DepartmentSerializer , RefillSerializer , SaleItemSerializer
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.decorators import action
from datetime import timedelta
from rest_framework import status
from django.db.models import Sum, Count , F , Avg
from django.utils.timezone import now 


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    
class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['department']
    search_fields = ['code_no','brand_name','generic_name']
    ordering_fields = ['expire_date','price','stock']


   # ---------------- BULK CREATE ----------------
    def create(self, request, *args, **kwargs):
        """
        If request.data is a list → bulk create.
        Otherwise → default single create.
        """
        if isinstance(request.data, list):
            serializer = self.get_serializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_bulk_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return super().create(request, *args, **kwargs)

    def perform_bulk_create(self, serializer):
        serializer.save()

    # ---------------- BULK UPDATE ----------------
    @action(detail=False, methods=['put'], url_path="bulk_update")
    def bulk_update(self, request):
        """
        Update multiple medicines at once using their `code_no`.
        """
        serializer = self.get_serializer(data=request.data, many=True)
        serializer.is_valid(raise_exception=True)

        updated_items = []
        for item in serializer.validated_data:
            code_no = item.get("code_no")
            if not code_no:
                continue
            Medicine.objects.filter(code_no=code_no).update(**item)
            updated_items.append(code_no)

        return Response({"updated": updated_items}, status=200)

    # ---------------- CUSTOM ACTIONS ----------------
    @action(detail=False, methods=['get'])
    def expired(self, request):
        today = timezone.now().date()
        expired = Medicine.objects.filter(expire_date__lt=today)
        serializer = self.get_serializer(expired, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def nearly_expired(self, request):
        today = timezone.now().date()
        near_date = today + timedelta(days=30)
        nearly_expired = Medicine.objects.filter(expire_date__gte=today, expire_date__lte=near_date)
        serializer = self.get_serializer(nearly_expired, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def low_stock(self, request):
        low_stock = Medicine.objects.filter(stock__lte=10, stock__gt=0)
        serializer = self.get_serializer(low_stock, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stock_out(self, request):
        stock_out = Medicine.objects.filter(stock=0)
        serializer = self.get_serializer(stock_out, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def stock(self, request):
        medicines = Medicine.objects.all()
        data = [{"code_no": m.code_no, "brand_name": m.brand_name, "stock": m.stock} for m in medicines]
        return Response(data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

class RefillViewSet(viewsets.ModelViewSet):
    queryset = Refill.objects.all().order_by("-refill_date")
    serializer_class = RefillSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Automatically set the creator and update medicine stock
        refill = serializer.save(created_by=self.request.user)

        # Update medicine stock when refilled
        medicine = refill.medicine
        medicine.stock += refill.quantity
        medicine.price = refill.price  # Optionally update current price
        medicine.save()

class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().prefetch_related("items")
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]

    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['sold_by']
    search_fields = ['customer_name', 'customer_phone']
    ordering_fields = ['sale_date', 'total_amount']

    @action(detail=True, methods=["get"])
    def receipt(self, request, pk=None):
        """Generate a receipt for a sale"""
        sale = self.get_object()
        serializer = self.get_serializer(sale)
        return Response({
            "receipt": {
                "sale_id": sale.id,
                "customer": sale.customer_name,
                "phone": sale.customer_phone,
                "sold_by": sale.sold_by.username if sale.sold_by else None,
                "date": sale.sale_date,
                "discount": str(sale.discount),
                "total": str(sale.total_amount),
                "items": serializer.data["items"],
            }
        })
    
class DashboardViewSet(viewsets.ViewSet):
    """
    Dashboard API: Provides stock, sales, and department summaries
    """

    @action(detail=False, methods=["get"])
    def overview(self, request):
        today = now().date()
        near_expiry_threshold = today + timedelta(days=30)

        # --- Stock summaries ---
        total_medicines = Medicine.objects.count()
        low_stock = Medicine.objects.filter(stock__lte=10, stock__gt=0).count()
        stock_out = Medicine.objects.filter(stock=0).count()
        expired = Medicine.objects.filter(expire_date__lt=today).count()
        near_expiry = Medicine.objects.filter(
            expire_date__gte=today, expire_date__lte=near_expiry_threshold
        ).count()

        # --- Sales summaries ---
        today_sales_qty = (
            SaleItem.objects.filter(sale__sale_date__date=today)
            .aggregate(total=Sum("quantity"))["total"] or 0
        )
        total_sales_qty = SaleItem.objects.aggregate(total=Sum("quantity"))["total"] or 0

        revenue_today = (
            Sale.objects.filter(sale_date__date=today)
            .aggregate(revenue=Sum("total_amount"))["revenue"] or 0
        )
        total_revenue = (
            Sale.objects.aggregate(revenue=Sum("total_amount"))["revenue"] or 0
        )

        # --- Top 5 selling medicines ---
        top_selling = (
            SaleItem.objects.values("medicine__brand_name")
            .annotate(total_sold=Sum("quantity"))
            .order_by("-total_sold")[:5]
        )

        # --- Department stats ---
        department_stats = (
            Medicine.objects.values("department__name")
            .annotate(total=Count("id"))
            .order_by("department__name")
        )

        return Response({
            "stock": {
                "total_medicines": total_medicines,
                "low_stock": low_stock,
                "stock_out": stock_out,
                "expired": expired,
                "near_expiry": near_expiry,
            },
            "sales": {
                "today_sales_qty": today_sales_qty,
                "total_sales_qty": total_sales_qty,
                "revenue_today": revenue_today,
                "total_revenue": total_revenue,
            },
            "top_selling": list(top_selling),
            "departments": list(department_stats),
        })

    @action(detail=False, methods=["get"])
    def analytics(self, request):
        today = now().date()
        last_week = today - timedelta(days=7)
        near_expiry_threshold = today + timedelta(days=30)

        # --- Revenue and Transactions ---
        total_revenue = Sale.objects.aggregate(total=Sum("total_amount"))["total"] or 0
        total_transactions = Sale.objects.count()
        avg_order_value = (
            Sale.objects.aggregate(avg=Avg("total_amount"))["avg"] or 0
        )
        inventory_value = Medicine.objects.aggregate(
            total=Sum(F("stock") * F("price"))
        )["total"] or 0

        # --- Sales Trend (last 7 days) ---
        sales_trend = (
            Sale.objects.filter(sale_date__date__gte=last_week)
            .extra(select={"day": "date(sale_date)"})
            .values("day")
            .annotate(total_sales=Sum("total_amount"))
            .order_by("day")
        )

        # --- Inventory by Category (department) ---
        inventory_by_category = (
            Medicine.objects.values("department__name")
            .annotate(value=Sum(F("stock") * F("price")))
            .order_by("department__name")
        )

        # --- Top Selling Products ---
        top_selling = (
            SaleItem.objects.values("medicine__brand_name")
            .annotate(total_sold=Sum("quantity"))
            .order_by("-total_sold")[:5]
        )

        # --- Stock Alerts ---
        low_stock = Medicine.objects.filter(stock__lte=10, stock__gt=0)
        stock_out = Medicine.objects.filter(stock=0)
        near_expiry = Medicine.objects.filter(
            expire_date__gte=today, expire_date__lte=near_expiry_threshold
        )

        # --- Weekly Summary ---
        week_sales = (
            Sale.objects.filter(sale_date__date__gte=last_week)
            .aggregate(total=Sum("total_amount"))
        )["total"] or 0
        week_transactions = (
            Sale.objects.filter(sale_date__date__gte=last_week).count()
        )

        # --- Inventory Health ---
        total_products = Medicine.objects.count()

        # --- Performance Metrics (example) ---
        profit_margin = 24.5  # Placeholder
        inventory_turnover = (
            total_revenue / inventory_value if inventory_value > 0 else 0
        )
        customer_satisfaction = 94.2  # Example static value

        return Response({
            "summary": {
                "total_revenue": total_revenue,
                "total_transactions": total_transactions,
                "avg_order_value": avg_order_value,
                "inventory_value": inventory_value,
            },
            "sales_trend": list(sales_trend),
            "inventory_by_category": list(inventory_by_category),
            "top_selling": list(top_selling),
            "stock_alerts": {
                "low_stock": list(low_stock.values("brand_name", "stock")),
                "stock_out": list(stock_out.values("brand_name")),
                "near_expiry": list(near_expiry.values("brand_name", "expire_date")),
            },
            "weekly_summary": {
                "week_sales": week_sales,
                "transactions": week_transactions,
                "new_customers": 28,  # Replace if customer model exists
            },
            "inventory_health": {
                "total_products": total_products,
                "low_stock": low_stock.count(),
                "near_expiry": near_expiry.count(),
                "stock_out": stock_out.count(),
            },
            "performance_metrics": {
                "profit_margin": profit_margin,
                "inventory_turnover": round(inventory_turnover, 2),
                "customer_satisfaction": customer_satisfaction,
            },
        })