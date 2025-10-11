from django.db import models
from django.conf import settings
from django.utils import timezone
from django.utils.timezone import now
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid


class Department(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=255)

    def __str__(self):
        return f"{self.code} - {self.name}"


class Medicine(models.Model):
    class UnitChoices(models.TextChoices):
        PK = "Pk", "Pk"
        BOTTLE = "Bottle", "Bottle"
        SACHET = "Sachet", "Sachet"
        AMPULE = "Ampule", "Ampule"
        VIAL = "Vial", "Vial"
        TIN = "Tin", "Tin"
        STRIP = "Strip", "Strip"
        TUBE = "Tube", "Tube"
        BOX = "Box", "Box"
        COSMETICS = "Cosmetics", "Cosmetics"
        TEN_X_100 = "10 x 100", "10 x 100"
        OF_10 = "Of 10", "Of 10"
        OF_20 = "Of 20", "Of 20"
        OF_14 = "Of 14", "Of 14"
        OF_28 = "Of 28", "Of 28"
        OF_30 = "Of 30", "Of 30"
        SUPPOSITORY = "Suppository", "Suppository"
        PCS = "Pcs", "Pcs"

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
    company_name = models.CharField(max_length=255, blank=True, null=True)
    FSNO = models.CharField(blank=True, null=True)
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True)
    attachment = models.FileField(upload_to="medicine_attachments/", blank=True, null=True)

    # ✅ new enum field for unit
    unit = models.CharField(
        max_length=20,
        choices=UnitChoices.choices,
        default=UnitChoices.PCS,
        editable=True  # change to False if you don't want admins to edit in admin
    )

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
        return self.refills.count()

    def __str__(self):
        return f"{self.brand_name} ({self.code_no})"


class Sale(models.Model):
    PAYMENT_METHOD_CHOICES = [
        ('cash', 'Cash'),
        ('transfer', 'Bank Transfer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sold_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    customer_name = models.CharField(max_length=255, blank=True, null=True)
    customer_phone = models.CharField(max_length=20, blank=True, null=True)
    sale_date = models.DateTimeField(auto_now_add=True)

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='cash',
    )

    discount_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
    )
    base_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discounted_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    discounted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discounted_sales",
    )

    def calculate_totals(self):
        subtotal = sum(Decimal(item.quantity) * item.price for item in self.items.all())
        self.base_price = subtotal
        self.discounted_amount = (subtotal * self.discount_percentage) / Decimal(100)
        self.total_amount = subtotal - self.discounted_amount

    def save(self, *args, **kwargs):
        self.calculate_totals()
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Sale {self.id} - {self.customer_name or 'Walk-in Customer'}"



class SaleItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sale = models.ForeignKey(Sale, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField()
    price = models.DecimalField(max_digits=12, decimal_places=2)

    @property
    def total_price(self):
        return self.price * self.quantity

    def __str__(self):
        return f"{self.medicine.brand_name} x {self.quantity}"


def today():
    return now().date()


class Refill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    medicine = models.ForeignKey("Medicine", on_delete=models.CASCADE, related_name="refills")
    department = models.ForeignKey("Department", on_delete=models.SET_NULL, null=True)

    batch_no = models.CharField(max_length=100)
    manufacture_date = models.DateField()
    expire_date = models.DateField()
    price = models.DecimalField(
        max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))]
    )
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])

    refill_date = models.DateField(default=today)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)

    def __str__(self):
        return f"Refill for {self.medicine.brand_name} (Batch {self.batch_no})"
