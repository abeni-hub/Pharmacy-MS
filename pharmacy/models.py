from django.db import models
from django.conf import settings
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator

class Department(models.Model):
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code} - {self.name}"

class Medicine(models.Model):
    code_no = models.CharField(max_length=50, unique=True)
    brand_name = models.CharField(max_length=255)
    generic_name = models.CharField(max_length=255, blank=True, null=True)
    batch_no = models.CharField(max_length=100, blank=True, null=True)
    manufacture_date = models.DateField()
    expire_date = models.DateField()
    price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal('0.00'))])
    stock = models.IntegerField(default=0)
    low_stock_threshold = models.IntegerField(default=10)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True)
    attachment = models.FileField(upload_to='medicine_attachments/', blank=True, null=True)

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

    def __str__(self):
        return f"{self.brand_name} ({self.code_no})"

class Sale(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    total_price = models.DecimalField(max_digits=12, decimal_places=2)
    sold_at = models.DateTimeField(auto_now_add=True)
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)

    def save(self, *args, **kwargs):
        # reduce stock
        if self.pk is None:  # new sale
            if self.medicine.stock < self.quantity:
                raise ValueError("Not enough stock")
            self.medicine.stock -= self.quantity
            self.medicine.save()
            self.total_price = self.medicine.price * self.quantity
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale of {self.medicine.brand_name} ({self.quantity})"

class Refill(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="refills")
    batch_no = models.CharField(max_length=100)
    refill_date = models.DateField(default=timezone.localdate)
    end_date = models.DateField(help_text="Expiry date of this batch")
    price = models.DecimalField(max_digits=12, decimal_places=2)

    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True
    )

    def __str__(self):
        return f"Refill for {self.medicine.brand_name} ({self.batch_no})"
