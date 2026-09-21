from django.db import models
from django.core.validators import MinValueValidator

# Create your models here.

class Product(models.Model):
    vendor = models.ForeignKey(
        'accounts.VendorProfile', 
        related_name='products', 
        on_delete=models.CASCADE
        )
    name = models.CharField(max_length=255)
    price = models.DecimalField(
        validators=[MinValueValidator(0.01)],
        max_digits=10,
          decimal_places=2
          )
    description = models.TextField(blank=True, null=True)
    category = models.CharField(max_length=255, blank=True, null=True)
    in_stock = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return self.name
