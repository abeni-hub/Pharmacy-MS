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
    total_price = serializers.SerializerMethodField()

    class Meta:
        model = SaleItem
        fields = ["id", "medicine", "medicine_name", "quantity", "price", "total_price"]

    def get_total_price(self, obj):
        return str(Decimal(obj.quantity) * obj.price)


class SaleSerializer(serializers.ModelSerializer):
    items = SaleItemSerializer(many=True, required=False)
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
            "discount_percentage",
            "base_price",
            "discounted_amount",
            "discounted_by",
            "total_amount",
            "items",
        ]

    def create(self, validated_data):
        items_data = validated_data.pop("items", [])
        user = self.context["request"].user

        validated_data["sold_by"] = user
        validated_data["discounted_by"] = user

        sale = Sale.objects.create(**validated_data)

        subtotal = Decimal(0)
        for item_data in items_data:
            medicine = item_data["medicine"]
            qty = item_data["quantity"]

            # ✅ Stock check
            if medicine.stock < qty:
                raise serializers.ValidationError(
                    f"Not enough stock for {medicine.brand_name}. Available: {medicine.stock}"
                )

            medicine.stock -= qty
            medicine.save()

            sale_item = SaleItem.objects.create(sale=sale, **item_data)
            subtotal += sale_item.quantity * sale_item.price

        # ✅ Apply discount
        discount_factor = (Decimal(100) - sale.discount_percentage) / Decimal(100)
        sale.base_price = subtotal
        sale.total_amount = subtotal * discount_factor
        sale.discounted_amount = subtotal - sale.total_amount
        sale.save()

        return sale

    def update(self, instance, validated_data):
        items_data = validated_data.pop("items", None)
        user = self.context["request"].user

        # 🔹 update who last applied discount
        instance.discounted_by = user

        # update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()

        subtotal = Decimal(0)
        if items_data is not None:
            # rollback old stock
            for old_item in instance.items.all():
                old_item.medicine.stock += old_item.quantity
                old_item.medicine.save()
            instance.items.all().delete()

            # add new items
            for item_data in items_data:
                medicine = item_data["medicine"]
                qty = item_data["quantity"]

                if medicine.stock < qty:
                    raise serializers.ValidationError(
                        f"Not enough stock for {medicine.brand_name}. Available: {medicine.stock}"
                    )

                medicine.stock -= qty
                medicine.save()

                sale_item = SaleItem.objects.create(sale=instance, **item_data)
                subtotal += sale_item.quantity * sale_item.price
        else:
            # recalc from existing items
            subtotal = sum(
                Decimal(item.quantity) * item.price for item in instance.items.all()
            )

        # ✅ recalc totals
        discount_factor = (Decimal(100) - instance.discount_percentage) / Decimal(100)
        instance.base_price = subtotal
        instance.total_amount = subtotal * discount_factor
        instance.discounted_amount = subtotal - instance.total_amount
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