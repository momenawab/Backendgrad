"""
Views for Authentication app.
"""
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.authtoken.models import Token
from django.contrib.auth import login, logout
from .models import User, WorkerProfile, WorkerAccount
from .serializers import (
    UserSerializer,
    WorkerProfileSerializer,
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer,
    CreateWorkerAccountSerializer,
    WorkerLoginResponseSerializer,
)


class RegisterView(generics.CreateAPIView):
    """
    API endpoint for user registration.
    POST /api/auth/register/
    """
    queryset = User.objects.all()
    permission_classes = [AllowAny]
    serializer_class = RegisterSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        # Log the user in after registration
        login(request, user)

        return Response({
            'message': 'Registration successful.',
            'user': UserSerializer(user).data
        }, status=status.HTTP_201_CREATED)


class LoginView(generics.GenericAPIView):
    """
    API endpoint for user login.
    POST /api/auth/login/

    Returns user data with role. If role='worker', includes worker profile.
    Frontend determines routing based on role.
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        login(request, user)

        # Create or get auth token for API authentication
        token, _ = Token.objects.get_or_create(user=user)

        response_data = {
            'message': 'Login successful.',
            'token': token.key,
            'user': UserSerializer(user).data
        }

        # If worker, include worker profile data
        if user.role == 'worker' and hasattr(user, 'worker_account'):
            worker = user.worker_account.worker
            response_data['worker'] = {
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

        return Response(response_data, status=status.HTTP_200_OK)


class LogoutView(generics.GenericAPIView):
    """
    API endpoint for user logout.
    POST /api/auth/logout/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        logout(request)
        return Response({
            'message': 'Logout successful.'
        }, status=status.HTTP_200_OK)


class ProfileView(generics.RetrieveUpdateAPIView):
    """
    API endpoint for getting/updating current user profile.
    GET /api/auth/profile/
    PUT /api/auth/profile/
    """
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return self.request.user


class ChangePasswordView(generics.GenericAPIView):
    """
    API endpoint for changing password.
    POST /api/auth/change-password/
    """
    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        user.set_password(serializer.validated_data['new_password'])
        user.save()

        return Response({
            'message': 'Password changed successfully.'
        }, status=status.HTTP_200_OK)


class WorkerProfileListView(generics.ListCreateAPIView):
    """
    API endpoint for listing and creating worker profiles.
    GET /api/auth/workers/
    POST /api/auth/workers/
    """
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return WorkerProfile.objects.filter(is_active=True)


class WorkerProfileDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for worker profile details.
    GET /api/auth/workers/{id}/
    PUT /api/auth/workers/{id}/
    DELETE /api/auth/workers/{id}/
    """
    serializer_class = WorkerProfileSerializer
    permission_classes = [IsAuthenticated]
    lookup_field = 'id'

    def get_queryset(self):
        return WorkerProfile.objects.all()


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me_view(request):
    """
    Simple endpoint to get current user info.
    GET /api/auth/me/
    """
    return Response({
        'user': UserSerializer(request.user).data,
        'worker_profile': WorkerProfileSerializer(
            request.user.worker_profile
        ).data if hasattr(request.user, 'worker_profile') else None
    })


DEFAULT_SETTINGS = {
    'language': 'en',
    'theme': 'light',
    'notifications': {'in_app': True, 'email': False, 'sms': False},
}

DEFAULT_NOTIFICATION_PREFERENCES = {
    'enableAll': True,
    'doNotDisturb': False,
    'alerts': {
        'hardHat': True,
        'vest': True,
        'gloves': True,
        'steelToedBoots': True,
        'safetyGlasses': True,
        'earProtection': True,
    },
    'channels': {'in_app': True, 'email': False, 'sms': False},
    'emailReports': False,
    'reportFrequency': 'weekly',
}


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def settings_view(request):
    """
    GET/PUT /api/auth/settings/

    Per-user app settings: language, theme, account block, notification channels.
    The `account` block is backed by the User's name/email/phone fields; the rest
    lives in User.preferences (JSON).
    """
    user = request.user

    if request.method == 'PUT':
        data = request.data or {}
        prefs = {**DEFAULT_SETTINGS, **(user.preferences or {})}
        for key in ('language', 'theme', 'notifications'):
            if key in data:
                prefs[key] = data[key]
        user.preferences = prefs

        account = data.get('account') or {}
        if 'email' in account:
            user.email = account['email'] or ''
        if 'phone' in account:
            user.phone = account['phone']
        if 'name' in account and account['name']:
            parts = account['name'].split()
            user.first_name = parts[0]
            user.last_name = ' '.join(parts[1:]) if len(parts) > 1 else ''
        user.save()

    prefs = {**DEFAULT_SETTINGS, **(user.preferences or {})}
    return Response({
        'language': prefs.get('language'),
        'theme': prefs.get('theme'),
        'account': {
            'name': (f"{user.first_name} {user.last_name}".strip()) or user.username,
            'email': user.email,
            'phone': user.phone,
        },
        'notifications': prefs.get('notifications'),
    })


@api_view(['GET', 'PUT'])
@permission_classes([IsAuthenticated])
def notification_preferences_view(request):
    """
    GET/PUT /api/auth/notification-preferences/

    Per-user notification preferences stored in User.notification_preferences (JSON).
    """
    user = request.user

    if request.method == 'PUT':
        merged = {**DEFAULT_NOTIFICATION_PREFERENCES, **(user.notification_preferences or {})}
        merged.update(request.data or {})
        user.notification_preferences = merged
        user.save(update_fields=['notification_preferences', 'updated_at'])

    return Response({**DEFAULT_NOTIFICATION_PREFERENCES, **(user.notification_preferences or {})})


class CreateWorkerAccountView(generics.GenericAPIView):
    """
    Admin creates a worker account.
    POST /api/auth/workers/create-account/

    Body:
        - worker_id: Link to existing Worker
        - username: Login username
        - password: Initial password
        - email: Optional

    Only admin/supervisor can create worker accounts.
    """
    permission_classes = [IsAuthenticated]
    serializer_class = CreateWorkerAccountSerializer

    def post(self, request, *args, **kwargs):
        # Only admin/supervisor can create worker accounts
        if request.user.role not in ['admin', 'supervisor']:
            return Response({
                'error': 'You do not have permission to create worker accounts.'
            }, status=status.HTTP_403_FORBIDDEN)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        worker_account = serializer.save()

        return Response({
            'message': 'Worker account created successfully.',
            'worker_account': {
                'id': worker_account.id,
                'username': worker_account.user.username,
                'worker_id': worker_account.worker.worker_id,
                'worker_name': worker_account.worker.name,
            }
        }, status=status.HTTP_201_CREATED)
