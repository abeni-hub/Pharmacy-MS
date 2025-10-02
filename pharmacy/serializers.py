from rest_framework import serializers
from .models import Medicine, Sale, Department , Refill , SaleItem

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
    items = SaleItemSerializer(many=True)
    sold_by_name = serializers.CharField(source="sold_by.username", read_only=True)

    class Meta:
        model = Sale
        fields = [
            "id", "customer_name", "customer_phone", "discount",
            "total_amount", "sale_date", "sold_by", "sold_by_name", "items"
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items")
        sale = Sale.objects.create(**validated_data)

        total = 0
        for item in items_data:
            medicine = item["medicine"]
            quantity = item["quantity"]
            price = item["price"]

            SaleItem.objects.create(sale=sale, **item)
            total += price * quantity

        # apply discount
        sale.total_amount = total - sale.discount
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