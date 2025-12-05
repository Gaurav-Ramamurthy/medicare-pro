from django.contrib import admin
from patients.models import Patient
from medical.models import MedicalRecord


@admin.register(Patient)
class PatientAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "first_name",
        "last_name",
        "email",
        "phone",
        "date_of_birth",
        "created_at",
    )
    list_filter = ("created_at", "date_of_birth")
    search_fields = ("first_name", "last_name", "email", "phone")


@admin.register(MedicalRecord)
class MedicalRecordAdmin(admin.ModelAdmin):
    list_display = (
        "patient",
        "author",
        "file_description",
        "created_at",
        "is_active",
    )
    list_filter = ("is_active", "created_at")
    search_fields = (
        "patient__first_name",
        "patient__last_name",
        "author__username",
        "file_description",
        "content",
    )






from django.contrib import admin
from .models import ContactQuery

@admin.register(ContactQuery)
class ContactQueryAdmin(admin.ModelAdmin):
    list_display = ['full_name', 'email', 'phone', 'created_at', 'status']
    list_filter = ['status', 'created_at']
    search_fields = ['full_name', 'email', 'message']
    list_editable = ['status']
    ordering = ['-created_at']
