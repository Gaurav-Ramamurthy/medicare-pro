# dashboards/urls.py - Role-Based Dashboards
from django.urls import path
from . import views

urlpatterns = [
    # Role-Specific Dashboards
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('doctor-dashboard/', views.doctor_dashboard, name='doctor_dashboard'),
    path('reception-dashboard/', views.reception_dashboard, name='reception_dashboard'),
    path('dashboard/', views.dashboard, name='dashboard'),  # Default/Patient dashboard
    path('post-login-redirect/', views.post_login_redirect, name='post_login_redirect'),

]
