"""
Serializers for Workers app.
"""
from rest_framework import serializers
from .models import Worker, WorkerShift


class WorkerListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for worker listings."""
    photo_url = serializers.SerializerMethodField()

    class Meta:
        model = Worker
        fields = ['id', 'worker_id', 'name', 'department', 'position', 'photo_url']

    def get_photo_url(self, obj):
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
        return None


class WorkerSerializer(serializers.ModelSerializer):
    """Serializer for Worker model."""
    photo_url = serializers.SerializerMethodField()
    compliance_rate = serializers.ReadOnlyField()
    supervisor_name = serializers.SerializerMethodField()
    required_ppe_display = serializers.SerializerMethodField()
    face_photo_valid = serializers.BooleanField(read_only=True)

    class Meta:
        model = Worker
        fields = ['id', 'worker_id', 'name', 'email', 'phone',
                  'department', 'position', 'shift',
                  'photo', 'photo_url', 'required_ppe', 'required_ppe_display',
                  'hire_date', 'employee_id', 'supervisor', 'supervisor_name',
                  'is_active', 'notes', 'compliance_rate',
                  'face_photo_valid',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'compliance_rate']

    def get_photo_url(self, obj):
        """Get full photo URL."""
        if obj.photo:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.photo.url)
        return None

    def get_supervisor_name(self, obj):
        """Get supervisor name."""
        if obj.supervisor:
            return obj.supervisor.name
        return None

    def get_required_ppe_display(self, obj):
        """Get human-readable required PPE list."""
        return obj.get_required_ppe_display()


class WorkerCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating workers."""
    class Meta:
        model = Worker
        fields = ['worker_id', 'name', 'email', 'phone',
                  'department', 'position', 'shift',
                  'photo', 'required_ppe',
                  'hire_date', 'employee_id', 'supervisor',
                  'is_active', 'notes']

    def validate_worker_id(self, value):
        """Validate worker_id is unique."""
        if Worker.objects.filter(worker_id=value).exists():
            raise serializers.ValidationError("A worker with this ID already exists.")
        return value


class WorkerUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating workers."""
    class Meta:
        model = Worker
        fields = ['name', 'email', 'phone', 'department', 'position',
                  'shift', 'photo', 'required_ppe', 'hire_date',
                  'employee_id', 'supervisor', 'is_active', 'notes']


class WorkerShiftSerializer(serializers.ModelSerializer):
    """Serializer for WorkerShift model."""
    worker_name = serializers.SerializerMethodField()

    class Meta:
        model = WorkerShift
        fields = ['id', 'worker', 'worker_name', 'date', 'shift_type',
                  'check_in', 'check_out', 'violations_count',
                  'alerts_triggered', 'notes', 'created_at']
        read_only_fields = ['id', 'created_at']

    def get_worker_name(self, obj):
        """Get worker name."""
        return obj.worker.name


class WorkerDetailSerializer(WorkerSerializer):
    """Detailed serializer with shift information."""
    shifts = WorkerShiftSerializer(many=True, read_only=True)
    recent_violations = serializers.SerializerMethodField()

    class Meta(WorkerSerializer.Meta):
        fields = WorkerSerializer.Meta.fields + ['shifts', 'recent_violations']

    def get_recent_violations(self, obj):
        """Get recent violations for this worker."""
        from detection.models import ViolationRecord
        violations = ViolationRecord.objects.filter(
            worker_id=obj.worker_id
        ).order_by('-timestamp')[:5]
        return [
            {
                'violation_id': v.violation_id,
                'timestamp': v.timestamp,
                'missing_ppe': v.missing_ppe,
                'status': v.status
            }
            for v in violations
        ]
