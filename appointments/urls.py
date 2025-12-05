# appointments/urls.py - Complete Appointment System
from django.urls import path
from . import views

urlpatterns = [
    # Appointment List & CRUD
    path('', views.appointment_list, name='appointment_list'),
    path('add/', views.appointment_create, name='appointment_add'),
    path('<int:pk>/', views.appointment_detail, name='appointment_detail'),
    path('<int:pk>/edit/', views.appointment_edit, name='appointment_edit'),
    path('<int:pk>/delete/', views.appointment_delete, name='appointment_delete'),

    # Special Appointment Views
    path('daily/', views.daily_appointments_view, name='daily_appointments'),
    path('history/', views.appointment_history, name='appointment_history'),
    path('<int:pk>/reschedule/', views.appointment_reschedule, name='appointment_reschedule'),

    #calendar view
    path('calendar/', views.calendar_page, name='calendar_page'),
    path('calendar/events/', views.calendar_events, name='calendar_events'),
    
]
