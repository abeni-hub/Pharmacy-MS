from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from decimal import Decimal
from django.core.validators import MinValueValidator
import uuid


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code} - {self.name}"

class Medicine(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code_no = models.CharField(max_length=50, unique=True)
    brand_name = models.CharField(max_length=255)
    generic_name = models.CharField(max_length=255, blank=True, null=True)
    batch_no = models.CharField(max_length=100, blank=True, null=True)
    manufacture_date = models.DateField()
    expire_date = models.DateField()
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))]
    )
    stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True)
    attachment = models.FileField(upload_to="medicine_attachments/", blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def is_out_of_stock(self):
        return self.stock <= 0

    def is_expired(self):
        return timezone.localdate() > self.expire_date

    def is_nearly_expired(self, days=30):
        delta = (self.expire_date - timezone.localdate()).days
        return 0 <= delta <= days

    @property
    def refill_count(self):
        # Count how many times this medicine has been refilled
        return self.refills.count()

    def __str__(self):
        return f"{self.brand_name} ({self.code_no})"
class Sale(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    discount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    sale_date = models.DateTimeField(default=timezone.now)
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Sale #{self.id} - {self.sale_date.strftime('%Y-%m-%d')}"


class SaleItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)  # snapshot of price at sale time

    @property
    def total_price(self):
        return self.price * self.quantity
        


# class SaleItem(models.Model):
#     id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
#     sale = models.ForeignKey(Sale, related_name="items", on_delete=models.CASCADE)
#     medicine = models.ForeignKey("Medicine", on_delete=models.CASCADE)
#     quantity = models.PositiveIntegerField()
#     price = models.DecimalField(max_digits=12, decimal_places=2)  # snapshot of medicine price
#     subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)

#     def save(self, *args, **kwargs):
#         if self.pk is None:  # new item
#             if self.medicine.stock < self.quantity:
#                 raise ValueError("Not enough stock")
#             self.medicine.stock -= self.quantity
#             self.medicine.save()

#         self.subtotal = self.price * self.quantity
#         super().save(*args, **kwargs)

#     def __str__(self):
#         return f"{self.medicine.brand_name} x {self.quantity}"
def today():
    return now().date()


class Refill(models.Model):
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    medicine = models.ForeignKey(
        "Medicine", on_delete=models.CASCADE, related_name="refills"
    )
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True)

    batch_no = models.CharField(max_length=100)
    manufacture_date = models.DateField()
    expire_date = models.DateField()
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    refill_date = models.DateField(default=today)  # ✅ returns date object, no error
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Refill for {self.medicine.brand_name} (Batch {self.batch_no})"