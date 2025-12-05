# users/urls.py - Staff Directory & Management
from django.urls import path
from . import views

urlpatterns = [
    # Staff Directory
    path('staff-directory/', views.staff_directory, name='staff_directory'),
    
    # Staff CRUD
    path('staff/create/', views.create_user_view, name='create_user'),
    path('staff/edit/<int:pk>/', views.staff_edit_view, name='staff_edit'),
    path('staff/<int:pk>/delete/', views.staff_delete_view, name='staff_delete'),
]
