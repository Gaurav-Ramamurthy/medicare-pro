# medical/urls.py - Medical Record Management
from django.urls import path
from . import views

urlpatterns = [
    # Medical Record CRUD
    path('medical-record/<int:pk>/edit/', views.medical_record_edit, name='medical_record_edit'),
    path('medical-record/<int:pk>/delete/', views.medical_record_delete, name='medical_record_delete'),
]
