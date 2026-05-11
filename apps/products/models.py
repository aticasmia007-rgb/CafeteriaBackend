import uuid

from django.db import models


class Product(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField()
    price = models.DecimalField(max_digits=10, decimal_places=2)
    category = models.ManyToManyField(
        'categories.Category',
        blank=True,
        related_name='products',
    )
    allergens = models.ManyToManyField(
        'allergens.Allergen',
        blank=True,
        related_name='products',
    )
    image = models.URLField(blank=True, default='')
    available = models.BooleanField(default=True)
    stock = models.IntegerField(default=0)
    prepare_required = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
