from rest_framework import serializers
from .models import Medicine, Sale, Department, Refill, SaleItem
from decimal import Decimal


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'code', 'name']


class MedicineSerializer(serializers.ModelSerializer):
    is_out_of_stock = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    is_nearly_expired = serializers.SerializerMethodField()
    refill_count = serializers.SerializerMethodField()
    
    # ✅ show both value and label for unit
    unit_display = serializers.CharField(source='get_unit_display', read_only=True)

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

    def get_total_price(self, obj):
        return str(Decimal(obj.quantity) * obj.price)


class SaleSerializer(serializers.ModelSerializer):
    # ✅ Make items read_only so DRF doesn't try to assign them automatically
    items = SaleItemSerializer(many=True, read_only=True)
    base_price = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discounted_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    discounted_by = serializers.CharField(source="discounted_by.username", read_only=True)
    total_amount = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "customer_name",
            "customer_phone",
            "sale_date",
            "payment_method",
            "discount_percentage",
            "base_price",
            "discounted_amount",
            "discounted_by",
            "total_amount",
            "items",
        ]

    def create(self, validated_data):
        # ✅ get the items from initial_data (manual)
        items_data = self.initial_data.get("items", [])
        user = self.context["request"].user

        sale = Sale.objects.create(
            sold_by=user,
            discounted_by=user,
            **validated_data,
        )

        # ✅ create SaleItems manually
        for item in items_data:
            SaleItem.objects.create(
                sale=sale,
                medicine_id=item["medicine"],
                quantity=item["quantity"],
                price=item["price"],
            )

        # ✅ calculate totals after items created
        sale.calculate_totals()
        sale.save(update_fields=["base_price", "discounted_amount", "total_amount"])

        return sale

    def update(self, instance, validated_data):
        items_data = self.initial_data.get("items", None)
        user = self.context["request"].user
        instance.discounted_by = user

        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        # Handle sale items update manually
        if items_data is not None:
            # First restore stock for all existing items
            for old_item in instance.items.all():
                old_item.medicine.stock += old_item.quantity
                old_item.medicine.save(update_fields=["stock"])
                old_item.delete()

            # Create new sale items (stock will be deducted in SaleItem.save())
            for item in items_data:
                SaleItem.objects.create(
                    sale=instance,
                    medicine_id=item["medicine"],
                    quantity=item["quantity"],
                    price=item["price"],
                )

        instance.calculate_totals()
        instance.save(update_fields=["base_price", "discounted_amount", "total_amount"])
        return instance
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
