"""
Worker management models for SafeSight PPE Detection System.
"""
from django.db import models
from django.conf import settings
import os


def worker_photo_upload_path(instance, filename):
    """Generate upload path for worker photos."""
    ext = os.path.splitext(filename)[1]
    return f'workers/photos/{instance.worker_id}{ext}'


class Worker(models.Model):
    """
    Worker profiles with PPE requirements and tracking.
    """
    DEPARTMENT_CHOICES = [
        ('construction', 'Construction'),
        ('manufacturing', 'Manufacturing'),
        ('maintenance', 'Maintenance'),
        ('warehouse', 'Warehouse'),
        ('laboratory', 'Laboratory'),
        ('cleaning', 'Cleaning'),
        ('other', 'Other'),
    ]

    SHIFT_CHOICES = [
        ('day', 'Day Shift'),
        ('night', 'Night Shift'),
        ('rotating', 'Rotating Shift'),
        ('flexible', 'Flexible'),
    ]

    worker_id = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Unique worker identifier"
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(blank=True, null=True)
    phone = models.CharField(max_length=20, blank=True, null=True)

    department = models.CharField(
        max_length=50,
        choices=DEPARTMENT_CHOICES,
        blank=True,
        null=True
    )
    position = models.CharField(max_length=100, blank=True, null=True)
    shift = models.CharField(
        max_length=20,
        choices=SHIFT_CHOICES,
        default='day'
    )

    # Photo for face recognition
    photo = models.ImageField(
        upload_to=worker_photo_upload_path,
        blank=True,
        null=True,
        help_text="Worker photo for identification"
    )

    # Face recognition fields
    # Legacy single 128-d dlib encoding (kept for backwards compatibility;
    # no longer used for matching once a worker has ArcFace embeddings).
    face_encoding = models.JSONField(
        blank=True,
        null=True,
        help_text="Legacy 128-d dlib encoding (deprecated)"
    )

    # One or more L2-normalized ArcFace embeddings (512-d each), captured from
    # multiple angles for robust recognition.
    face_embeddings = models.JSONField(
        default=list,
        blank=True,
        help_text="List of L2-normalized face embedding vectors"
    )

    # Identifier of the model that produced face_embeddings (e.g.
    # 'arcface_buffalo_l') so stale embeddings can be detected and ignored.
    embedding_model = models.CharField(
        max_length=50,
        blank=True,
        default='',
        help_text="Model id that produced the stored embeddings"
    )

    face_photo_valid = models.BooleanField(
        default=False,
        help_text="Whether the photo contains a valid detectable face"
    )

    # PPE requirements as JSON
    # e.g., ["hardHat", "vest", "gloves", "steelToedBoots"]
    required_ppe = models.JSONField(
        default=list,
        blank=True,
        help_text="List of required PPE types for this worker"
    )

    # Employment info
    hire_date = models.DateField(blank=True, null=True)
    employee_id = models.CharField(max_length=50, blank=True, null=True)
    supervisor = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subordinates'
    )

    # Status
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, null=True)
    # F7 — flag set when this worker has been assigned safety re-training
    # (driven by the repeat-offender risk score).
    training_assigned = models.BooleanField(default=False)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_workers'
    )

    class Meta:
        db_table = 'workers'
        verbose_name_plural = "Workers"
        ordering = ['name']
        indexes = [
            models.Index(fields=['worker_id']),
            models.Index(fields=['department']),
            models.Index(fields=['is_active']),
        ]

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

    @property
    def compliance_rate(self):
        """Calculate worker's compliance rate based on violations."""
        from detection.models import ViolationRecord
        total = ViolationRecord.objects.filter(worker_id=self.worker_id).count()
        resolved = ViolationRecord.objects.filter(
            worker_id=self.worker_id,
            status='resolved'
        ).count()
        if total == 0:
            return 100.0
        return round((resolved / total) * 100, 2)


class WorkerShift(models.Model):
    """
    Worker shift schedules for tracking and reporting.
    """
    worker = models.ForeignKey(
        Worker,
        on_delete=models.CASCADE,
        related_name='shifts'
    )
    date = models.DateField(db_index=True)
    shift_type = models.CharField(
        max_length=20,
        choices=Worker.SHIFT_CHOICES
    )
    check_in = models.TimeField(blank=True, null=True)
    check_out = models.TimeField(blank=True, null=True)

    # Detection stats for the shift
    violations_count = models.IntegerField(default=0)
    alerts_triggered = models.IntegerField(default=0)

    notes = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'worker_shifts'
        verbose_name_plural = "Worker Shifts"
        ordering = ['-date', 'shift_type']
        unique_together = [['worker', 'date', 'shift_type']]

    def __str__(self):
        return f"{self.worker.name} - {self.date} ({self.shift_type})"
