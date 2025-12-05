# core/urls.py - AUTHENTICATION ONLY
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # AUTHENTICATION
    path('', views.landing_page, name='landing_page'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('forgot-password/', views.forgot_password_request, name='forgot-password'),
    path('verify-otp/', views.verify_otp, name='verify-otp'),
    path('account/settings/', views.account_settings, name='account-settings'),
    path('password/manage/', views.password_manage, name='password-manage'),
    path('contact-queries/', views.contact_queries_list, name='contact_queries'),
    
]
