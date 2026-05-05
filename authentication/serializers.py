"""
Serializers for Authentication app.
"""
from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, WorkerProfile, WorkerAccount


class UserSerializer(serializers.ModelSerializer):
    """Serializer for User model."""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name',
                  'role', 'phone', 'department', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class WorkerProfileSerializer(serializers.ModelSerializer):
    """Serializer for WorkerProfile model."""
    class Meta:
        model = WorkerProfile
        fields = ['id', 'worker_id', 'name', 'department', 'position',
                  'photo', 'required_ppe', 'is_active', 'hire_date',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class RegisterSerializer(serializers.ModelSerializer):
    """Serializer for user registration."""
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'password_confirm',
                  'first_name', 'last_name', 'role', 'phone', 'department']

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({"password": "Passwords don't match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class LoginSerializer(serializers.Serializer):
    """Serializer for user login."""
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            user = authenticate(username=username, password=password)
            if not user:
                raise serializers.ValidationError(
                    {"detail": "Invalid credentials. Please try again."}
                )
            if not user.is_active:
                raise serializers.ValidationError(
                    {"detail": "This user account has been disabled."}
                )
            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError({
                "detail": "Must include username and password."
            })


class ChangePasswordSerializer(serializers.Serializer):
    """Serializer for password change."""
    old_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password = serializers.CharField(required=True, style={'input_type': 'password'})
    new_password_confirm = serializers.CharField(required=True, style={'input_type': 'password'})

    def validate(self, attrs):
        if attrs['new_password'] != attrs['new_password_confirm']:
            raise serializers.ValidationError({"new_password": "Passwords don't match."})
        return attrs

    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect.")
        return value


class WorkerAccountSerializer(serializers.ModelSerializer):
    """Serializer for WorkerAccount model."""
    class Meta:
        model = WorkerAccount
        fields = ['id', 'fcm_token', 'device_id', 'enable_notifications',
                  'notify_on_violation', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class CreateWorkerAccountSerializer(serializers.Serializer):
    """Serializer for creating a worker account (admin only)."""
    worker_id = serializers.CharField(
        max_length=50,
        help_text="Worker ID to link the account to"
    )
    username = serializers.CharField(
        max_length=150,
        help_text="Login username for the worker"
    )
    password = serializers.CharField(
        max_length=128,
        style={'input_type': 'password'},
        help_text="Initial password for the worker"
    )
    email = serializers.EmailField(
        required=False,
        help_text="Optional email address"
    )

    def validate_worker_id(self, value):
        """Check if worker exists and doesn't already have an account."""
        from workers.models import Worker

        try:
            worker = Worker.objects.get(worker_id=value)
        except Worker.DoesNotExist:
            raise serializers.ValidationError(
                f"Worker with ID '{value}' does not exist."
            )

        if hasattr(worker, 'user_account'):
            raise serializers.ValidationError(
                f"Worker '{worker.name}' already has an account."
            )

        return value

    def validate_username(self, value):
        """Check if username is already taken."""
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError(
                "This username is already taken."
            )
        return value

    def create(self, validated_data):
        """Create User and WorkerAccount."""
        from workers.models import Worker

        worker_id = validated_data['worker_id']
        username = validated_data['username']
        password = validated_data['password']
        email = validated_data.get('email')

        # Get the worker
        worker = Worker.objects.get(worker_id=worker_id)

        # Create User with role='worker'
        user = User.objects.create_user(
            username=username,
            password=password,
            email=email or '',
            role='worker',
            first_name=worker.name.split()[0] if worker.name else '',
            last_name=' '.join(worker.name.split()[1:]) if len(worker.name.split()) > 1 else ''
        )

        # Create WorkerAccount linking User to Worker
        worker_account = WorkerAccount.objects.create(
            user=user,
            worker=worker
        )

        return worker_account


class WorkerLoginResponseSerializer(serializers.Serializer):
    """Serializer for worker login response including worker profile."""
    user = UserSerializer()
    worker = serializers.SerializerMethodField()

    def get_worker(self, obj):
        """Get worker profile data."""
        user = obj.get('user')
        if hasattr(user, 'worker_account'):
            worker = user.worker_account.worker
            return {
                'worker_id': worker.worker_id,
                'name': worker.name,
                'department': worker.department,
                'position': worker.position,
                'email': worker.email,
                'phone': worker.phone,
                'required_ppe': worker.required_ppe,
                'is_active': worker.is_active,
                'hire_date': worker.hire_date.isoformat() if worker.hire_date else None,
            }
        return None
