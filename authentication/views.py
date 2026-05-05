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
