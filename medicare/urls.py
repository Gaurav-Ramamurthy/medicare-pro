# medicare/urls.py
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect
from django.conf import settings
from django.conf.urls.static import static
from core.views import home


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', home, name='home'),
    # All apps included at root level
    path('', include('core.urls')),      # Auth + Core
    path('patients/', include('patients.urls')),      # /patients/, /patients/add/
    path('appointments/', include('appointments.urls')), # /appointments/, /appointments/add/
    path('users/', include('users.urls')),    # /users/staff-directory/
    path('medical/', include('medical.urls')),     # /medical/medical-record/
    path('dashboards/', include('dashboards.urls')), # /dashboards/admin-dashboard/

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)