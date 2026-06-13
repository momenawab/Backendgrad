"""
Models for the Content app.

Lightweight, admin-editable instructional content (the "How To Use" steps shown
on the website and the Flutter app), so the tutorial copy can change without a
client redeploy.
"""
from django.db import models


class HowToStep(models.Model):
    """A single ordered step in the "How to use SafeSight" guide."""

    order = models.PositiveIntegerField(default=0, db_index=True)
    title = models.CharField(max_length=200)
    description = models.TextField()
    image_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'how_to_steps'
        ordering = ['order']

    def __str__(self):
        return f"{self.order}. {self.title}"
