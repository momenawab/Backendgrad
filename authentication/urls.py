"""
URL configuration for Authentication app.
"""
from django.urls import path
from .views import (
    RegisterView,
    LoginView,
    LogoutView,
    ProfileView,
    ChangePasswordView,
    WorkerProfileListView,
    WorkerProfileDetailView,
    me_view,
    CreateWorkerAccountView,
)

urlpatterns = [
    path('register/', RegisterView.as_view(), name='register'),
    path('login/', LoginView.as_view(), name='login'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('profile/', ProfileView.as_view(), name='profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change-password'),
    path('me/', me_view, name='me'),
    path('workers/', WorkerProfileListView.as_view(), name='worker-list'),
    path('workers/<int:id>/', WorkerProfileDetailView.as_view(), name='worker-detail'),
    # Worker account creation (admin only)
    path('workers/create-account/', CreateWorkerAccountView.as_view(), name='worker-create-account'),
]
