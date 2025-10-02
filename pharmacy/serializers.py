from rest_framework import serializers
from .models import Medicine, Sale, Department , Refill , SaleItem
from decimal import Decimal

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'code', 'name']

class MedicineSerializer(serializers.ModelSerializer):
    is_out_of_stock = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    is_nearly_expired = serializers.SerializerMethodField()
    refill_count = serializers.SerializerMethodField()   # ✅ added here

    class Meta:
        model = Medicine
        fields = '__all__'

    def get_is_out_of_stock(self, obj):
        return obj.is_out_of_stock()

    def get_is_expired(self, obj):
        return obj.is_expired()

    def get_is_nearly_expired(self, obj):
        return obj.is_nearly_expired()
    
    def get_refill_count(self, obj):   # ✅ this now calls your property
        return obj.refill_count
    
class SaleItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = SaleItem
        fields = ["id", "medicine", "quantity", "price", "subtotal"]

class SaleItemSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source="medicine.brand_name", read_only=True)

    class Meta:
        model = SaleItem
        fields = ["id", "medicine", "medicine_name", "quantity", "price", "total_price"]
        read_only_fields = ["total_price"]


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, required=False)
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2, read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id",
            "customer_name",
            "sale_date",
            "discount_percentage",  # ✅ keep this, not `discount`
            "total_amount",
            "items",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        sale = Sale.objects.create(**validated_data)

        for item_data in items_data:
            medicine = item_data["medicine"]
            qty = item_data["quantity"]

            # ✅ Decrease stock
            if medicine.stock < qty:
                raise serializers.ValidationError(
                    f"Not enough stock for {medicine.brand_name}. Available: {medicine.stock}"
                )
            medicine.stock -= qty
            medicine.save()

            # Create sale item
            SaleItem.objects.create(sale=sale, **item_data)

        # ✅ Calculate total with discount_percentage
        subtotal = sum(
            Decimal(item.quantity) * item.price for item in sale.items.all()
        )
        discount_factor = (Decimal(100) - sale.discount_percentage) / Decimal(100)
        sale.total_amount = subtotal * discount_factor
        sale.save()

        return sale

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)

        # Update sale basic info
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        if items_data is not None:
            instance.items.all().delete()
            for item_data in items_data:
                medicine = item_data["medicine"]
                qty = item_data["quantity"]

                if medicine.stock < qty:
                    raise serializers.ValidationError(
                        f"Not enough stock for {medicine.brand_name}. Available: {medicine.stock}"
                    )
                medicine.stock -= qty
                medicine.save()

                SaleItem.objects.create(sale=instance, **item_data)

        # ✅ Recalculate total
        subtotal = sum(
            Decimal(item.quantity) * item.price for item in instance.items.all()
        )
        discount_factor = (Decimal(100) - instance.discount_percentage) / Decimal(100)
        instance.total_amount = subtotal * discount_factor
        instance.save()

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