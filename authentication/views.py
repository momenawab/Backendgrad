"""
Views for Authentication app.
"""
from rest_framework import status, generics
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated
from django.contrib.auth import login, logout
from rest_framework.authtoken.models import Token
from .models import User, WorkerProfile
from .serializers import (
    UserSerializer,
    WorkerProfileSerializer,
    RegisterSerializer,
    LoginSerializer,
    ChangePasswordSerializer
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
    """
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    def post(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data['user']
        login(request, user)

        # Create or get auth token for mobile clients
        token, _ = Token.objects.get_or_create(user=user)

        return Response({
            'message': 'Login successful.',
            'user': UserSerializer(user).data,
            'token': token.key,
        }, status=status.HTTP_200_OK)


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
