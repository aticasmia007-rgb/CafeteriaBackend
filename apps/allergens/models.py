from django.db import models


class Allergen(models.Model):
    allergen_id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255)
    icon = models.URLField(blank=True, default='')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name
