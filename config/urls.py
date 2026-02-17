"""
URL configuration for SafeSight PPE Detection System.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('authentication.urls')),
    path('api/detection/', include('detection.urls')),
    path('api/workers/', include('workers.urls')),
    path('api/alerts/', include('alerts.urls')),
    path('api/reports/', include('reports.urls')),
    path('api/', include('detection.urls')),  # For base detection endpoint
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
