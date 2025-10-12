from rest_framework import viewsets, permissions, filters
from django_filters.rest_framework import DjangoFilterBackend
from .models import Medicine, Sale, Department , Refill , SaleItem
from .serializers import MedicineSerializer, SaleSerializer, DepartmentSerializer , RefillSerializer , SaleItemSerializer
from rest_framework.response import Response
from django.utils import timezone
from rest_framework.decorators import action
from datetime import timedelta
from django.db import transaction
from rest_framework import status
from django.db.models import Sum, Count , F , Avg
from django.utils.timezone import now 
from .pagination import CustomPagination


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['code','name']  # ✅ customize fields as per your model
    search_fields = ['code','name']             # ✅ searchable fields
    ordering_fields = ['name', 'created_at', 'id']      # ✅ sortable fields
    ordering = ['-id']                                  # default order
    pagination_class = CustomPagination
    
class MedicineViewSet(viewsets.ModelViewSet):
    queryset = Medicine.objects.all()
    serializer_class = MedicineSerializer
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['department', 'unit']  # ✅ added unit filter
    search_fields = ['brand_name','generic_name','unit']  # ✅ searchable
    ordering_fields = ['expire_date','price','stock']



   # ---------------- BULK CREATE ----------------
    def create(self, request, *args, **kwargs):
        if isinstance(request.data, list):
            serializer = self.get_serializer(data=request.data, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_bulk_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return super().create(request, *args, **kwargs)

    def perform_bulk_create(self, serializer):
        serializer.save(created_by=self.request.user)

    # ---------------- BULK UPDATE (by id) ----------------
    @action(detail=False, methods=['put'], url_path="bulk_update")
    def bulk_update(self, request):
        """
        Update multiple medicines at once using their `id`.
        Request body: list of objects each containing 'id' and the fields to update.
        """
        if not isinstance(request.data, list):
            return Response({"detail": "Expected a list of items for bulk_update."}, status=400)

        updated_ids = []
        for item in request.data:
            mid = item.get("id")
            if not mid:
                continue
            try:
                med = Medicine.objects.get(id=mid)
            except Medicine.DoesNotExist:
                continue
            # do not allow updating created_by via this endpoint
            for k, v in item.items():
                if k == "id":
                    continue
                setattr(med, k, v)
            med.save()
            updated_ids.append(str(mid))
        return Response({"updated": updated_ids}, status=200)

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
        data = [{"id": str(m.id), "brand_name": m.brand_name, "department": {"code": m.department.code if m.department else None, "name": m.department.name if m.department else None}, "stock": m.stock} for m in medicines]
        return Response(data)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class RefillViewSet(viewsets.ModelViewSet):
    queryset = Refill.objects.all().order_by("-refill_date")
    serializer_class = RefillSerializer
    pagination_class = CustomPagination
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Automatically set the creator and update medicine stock
        refill = serializer.save(created_by=self.request.user)

        # Update medicine stock when refilled
        medicine = refill.medicine
        medicine.stock += refill.quantity
        medicine.price = refill.price  # Optionally update current price
        medicine.save()

# ---------------- SALE VIEWSET ----------------
class SaleViewSet(viewsets.ModelViewSet):
    queryset = Sale.objects.all().select_related("sold_by", "discounted_by")
    serializer_class = SaleSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = CustomPagination

    def get_serializer_context(self):
        # ensure serializer has request in context (we use request.user inside serializer)
        ctx = super().get_serializer_context()
        ctx.update({"request": self.request})
        return ctx

    def create(self, request, *args, **kwargs):
        """
        Single, atomic save call. Do NOT call serializer.save() more than once.
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            sale = serializer.save()
        # re-serialize the saved sale for output (includes items, totals)
        out_serializer = self.get_serializer(sale)
        return Response(out_serializer.data, status=status.HTTP_201_CREATED)
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
        avg_order_value = Sale.objects.aggregate(avg=Avg("total_amount"))["avg"] or 0
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

        # --- Inventory by Category ---
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
        week_transactions = Sale.objects.filter(sale_date__date__gte=last_week).count()

        # --- Inventory Health ---
        total_products = Medicine.objects.count()

        # --- Performance Metrics ---
        profit_margin = 24.5  # Example static placeholder
        inventory_turnover = total_revenue / inventory_value if inventory_value > 0 else 0
        customer_satisfaction = 94.2  # Example static placeholder

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