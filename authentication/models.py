"""
Authentication models for SafeSight PPE Detection System.
"""
from django.db import models
from django.contrib.auth.models import AbstractUser
import os


class User(AbstractUser):
    """
    Extended User model for SafeSight system.
    Uses username/password authentication as specified.
    """
    ROLE_CHOICES = [
        ('admin', 'Administrator'),
        ('supervisor', 'Supervisor'),
        ('operator', 'Operator'),
        ('viewer', 'Viewer'),
        ('worker', 'Worker'),
    ]

    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='viewer')
    phone = models.CharField(max_length=20, blank=True, null=True)
    department = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'auth_user'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"


def worker_photo_upload_path(instance, filename):
    """Generate upload path for worker photos."""
    ext = os.path.splitext(filename)[1]
    return f'workers/photos/{instance.worker_id}{ext}'


class WorkerProfile(models.Model):
    """
    Worker profile for tracking individual workers and their PPE requirements.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='worker_profile',
        null=True,
        blank=True
    )
    worker_id = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200)
    department = models.CharField(max_length=100, blank=True, null=True)
    position = models.CharField(max_length=100, blank=True, null=True)
    photo = models.ImageField(
        upload_to=worker_photo_upload_path,
        blank=True,
        null=True,
        help_text="Worker photo for face recognition"
    )

    # PPE requirements as JSON - stores array of required PPE types
    # e.g., ["hardHat", "vest", "gloves", "steelToedBoots"]
    required_ppe = models.JSONField(
        default=list,
        blank=True,
        help_text="List of required PPE types for this worker"
    )

    is_active = models.BooleanField(default=True)
    hire_date = models.DateField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'worker_profiles'
        verbose_name_plural = "Worker Profiles"
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.worker_id})"

    def get_required_ppe_display(self):
        """Return human-readable list of required PPE."""
        ppe_names = {
            'hardHat': 'Hard Hat',
            'safetyGlasses': 'Safety Glasses',
            'vest': 'Safety Vest',
            'gloves': 'Gloves',
            'steelToedBoots': 'Steel-Toed Boots',
            'earProtection': 'Ear Protection',
        }
        return [ppe_names.get(ppe, ppe) for ppe in self.required_ppe]


class WorkerAccount(models.Model):
    """
    Links a User account to a Worker profile for worker login functionality.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='worker_account'
    )
    worker = models.OneToOneField(
        'workers.Worker',
        on_delete=models.CASCADE,
        related_name='user_account'
    )

    # Device tokens for push notifications
    fcm_token = models.TextField(blank=True, null=True)
    device_id = models.CharField(max_length=200, blank=True, null=True)

    # Notification preferences
    enable_notifications = models.BooleanField(default=True)
    notify_on_violation = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'worker_accounts'
        verbose_name_plural = "Worker Accounts"

    def __str__(self):
        return f"WorkerAccount: {self.user.username} -> {self.worker.name}"
