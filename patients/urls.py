# patients/urls.py - Complete Patient Management
from django.urls import path
from . import views

urlpatterns = [
    # Patient List & CRUD
    path('', views.patient_list, name='patient_list'),
    path('add/', views.create_patient, name='patient_add'),
    path('register/', views.patient_register, name='patient_register'),
    path('<int:pk>/', views.patient_detail, name='patient_detail'),
    path('<int:pk>/edit/', views.patient_edit, name='patient_edit'),
    path('<int:pk>/delete/', views.patient_delete, name='patient_delete'),

    # Patient Requests
    path('requests/', views.patient_requests_list, name='patient_requests_list'),
    path('requests/<int:request_id>/approve/', views.patient_request_approve, name='patient_request_approve'),
    path('requests/<int:request_id>/reject/', views.patient_request_reject, name='patient_request_reject'),
    path('requests/ajax/<int:request_id>/<str:action>/', views.ajax_patient_action, name='ajax_patient_action'),

    # Patient Medical Records
    path('<int:pk>/records/', views.patient_medical_records, name='patient_medical_records'),
]
