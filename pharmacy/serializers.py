from rest_framework import serializers
from .models import Medicine, Sale, Department, Refill, SaleItem
from decimal import Decimal
from django.db import transaction
from django.utils.timezone import now


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'code', 'name']

class MedicineDepartmentSimpleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['code', 'name']

class MedicineSerializer(serializers.ModelSerializer):
    is_out_of_stock = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    is_nearly_expired = serializers.SerializerMethodField()
    refill_count = serializers.SerializerMethodField()
    
    # ✅ show both value and label for unit
    unit_display = serializers.CharField(source='get_unit_display', read_only=True)
     # instead of code_no, show department with code & name
    department = MedicineDepartmentSimpleSerializer(read_only=True)
    class Meta:
        model = Medicine
        fields = '__all__'  # includes 'unit'
        read_only_fields = ['id', 'created_at', 'updated_at']

    def get_is_out_of_stock(self, obj):
        return obj.is_out_of_stock()

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_is_nearly_expired(self, obj):
        return obj.is_nearly_expired()

    def get_refill_count(self, obj):
        return obj.refill_count


class SaleItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.brand_name", read_only=True)
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ["id", "medicine", "medicine_name", "quantity", "price", "total_price"]
        read_only_fields = ["id", "medicine_name", "total_price"]

    def get_total_price(self, obj):
        return str(Decimal(obj.quantity) * obj.price)


class SaleCreateItemSerializer(serializers.Serializer):
    """
    Serializer used inside SaleSerializer for incoming sale items.
    Accepts medicine (id), quantity, optionally price (unit price). If price not provided,
    medicine.price (current price) will be used.
    """
    medicine = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    price = serializers.DecimalField(max_digits=12, decimal_places=2, required=False)


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, read_only=True)
    input_items = SaleCreateItemSerializer(many=True, write_only=True, required=True)

    sold_by_username = serializers.CharField(source="sold_by.username", read_only=True)
    discounted_by_username = serializers.CharField(source="discounted_by.username", read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id", "sold_by", "sold_by_username",
            "customer_name", "customer_phone", "sale_date",
            "payment_method", "discount_percentage",
            "base_price", "discounted_amount", "total_amount",
            "discounted_by", "discounted_by_username",
            "items", "input_items",
        ]
        read_only_fields = [
            "id", "sale_date", "base_price", "discounted_amount",
            "total_amount", "items", "sold_by", "discounted_by"
        ]

    def validate_discount_percentage(self, value):
        if value is None:
            return Decimal("0.00")
        if value < 0 or value > 100:
            raise serializers.ValidationError("Discount must be between 0 and 100")
        return value

    def validate(self, attrs):
        if not attrs.get("input_items"):
            raise serializers.ValidationError({"input_items": "At least one sale item is required."})
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        """
        Create Sale and related SaleItems while updating stock ONCE.
        Idempotency guard: if sale already has items, do nothing (prevents duplicate runs).
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)
        items_data = validated_data.pop("input_items")

        # 1) Create sale record (totals will be updated after items created)
        sale = Sale.objects.create(
            sold_by=user,
            customer_name=validated_data.get("customer_name"),
            customer_phone=validated_data.get("customer_phone"),
            payment_method=validated_data.get("payment_method", "cash"),
            discount_percentage=validated_data.get("discount_percentage", Decimal("0.00")),
        )

        # IDENTITY CHECK: If for any reason this sale already has items (e.g. called twice),
        # we avoid creating duplicates and avoid re-decrementing stock.
        if sale.items.exists():
            return sale

        total_base = Decimal("0.00")

        # For each incoming item: lock its medicine row, validate stock, create SaleItem, decrement stock exactly once
        for idx, item in enumerate(items_data):
            med_id = item.get("medicine")
            qty = int(item.get("quantity", 0))
            if qty <= 0:
                raise serializers.ValidationError({"input_items": f"Invalid quantity at index {idx}."})

            # lock medicine row for update to prevent race conditions
            try:
                medicine = Medicine.objects.select_for_update().get(id=med_id)
            except Medicine.DoesNotExist:
                raise serializers.ValidationError({"input_items": f"Medicine {med_id} does not exist (index {idx})."})

            if medicine.stock < qty:
                raise serializers.ValidationError({"input_items": f"Insufficient stock for {medicine.brand_name}. Available: {medicine.stock}, requested: {qty}."})

            unit_price = Decimal(item.get("price")) if item.get("price") is not None else medicine.price

            # create sale item row
            SaleItem.objects.create(sale=sale, medicine=medicine, quantity=qty, price=unit_price)

            # decrement stock exactly once here and persist
            medicine.stock = medicine.stock - qty
            medicine.save(update_fields=["stock"])

            total_base += (unit_price * qty)

        # compute discount and totals
        discount_pct = sale.discount_percentage or Decimal("0.00")
        discounted_amount = (total_base * (discount_pct / Decimal("100"))).quantize(Decimal("0.01"))
        total_amount = (total_base - discounted_amount).quantize(Decimal("0.01"))

        sale.base_price = total_base.quantize(Decimal("0.01"))
        sale.discounted_amount = discounted_amount
        sale.total_amount = total_amount

        if discount_pct > 0 and user and user.is_authenticated:
            sale.discounted_by = user

        sale.save()
        return sale
class RefillSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.brand_name", read_only=True)
    department_name = serializers.CharField(source="department.name", read_only=True)
    created_by_username = serializers.CharField(source="created_by.username", read_only=True)

    class Meta:
        model = Refill
        fields = [
            "id",
            "medicine",
            "medicine_name",
            "department",
            "department_name",
            "batch_no",
            "manufacture_date",
            "expire_date",
            "price",
            "quantity",
            "refill_date",
            "created_at",
            "created_by",
            "created_by_username",
        ]
        read_only_fields = ["id", "created_at", "created_by"]
