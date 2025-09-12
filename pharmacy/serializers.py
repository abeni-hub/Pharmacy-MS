from rest_framework import serializers
from .models import Medicine, Sale, Department

class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ['id', 'code', 'name']

class MedicineSerializer(serializers.ModelSerializer):
    is_out_of_stock = serializers.SerializerMethodField()
    is_expired = serializers.SerializerMethodField()
    is_nearly_expired = serializers.SerializerMethodField()

    class Meta:
        model = Medicine
        fields = '__all__'

    def get_is_out_of_stock(self, obj): return obj.is_out_of_stock()
    def get_is_expired(self, obj): return obj.is_expired()
    def get_is_nearly_expired(self, obj): return obj.is_nearly_expired()

class SaleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Sale
        fields = '__all__'
        read_only_fields = ['total_price', 'sold_at', 'sold_by']

    def create(self, validated_data):
        request = self.context.get('request')
        validated_data['sold_by'] = request.user
        return super().create(validated_data)
